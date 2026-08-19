from datetime import UTC, datetime
from pathlib import Path

import pytest

from asagent.cli import _alembic_config_path, build_persistent_agent_runtime
from asagent.core.conversation import Conversation
from asagent.core.conversation_file_scope import ConversationFileScope
from asagent.core.ids import ConversationId, UserId
from asagent.core.run_status import RunStatus
from asagent.models.contracts import ModelMessageRole, ModelResponse, ModelToolCall
from asagent.models.fake_provider import FakeModelProvider
from asagent.paths import AppPaths
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.sqlite.conversation_file_scope_repository import (
    SqliteConversationFileScopeRepository,
)
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.database import upgrade_sqlite_database
from asagent.storage.sqlite.file_change_repository import SqliteFileChangeRepository
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.tools.approval import ToolApprovalRequest, ToolApprovalRequestedCallback
from asagent.workspace.settings import ConversationWorkspaceSettings


class AllowAllApprovals:
    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        if on_requested is not None:
            await on_requested(request)
        return True


@pytest.mark.asyncio
async def test_runtime_uses_only_the_current_conversations_file_scope(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    paths.workspace_dir.mkdir(parents=True)
    external_folder = tmp_path / "shared-folder"
    external_folder.mkdir()
    external_file = tmp_path / "outside-workspace.txt"
    external_file.write_text("conversation one only", encoding="utf-8")
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )
    conversations = SqliteConversationRepository(database_path)
    scopes = SqliteConversationFileScopeRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    first_conversation = ConversationId("conversation-1")
    second_conversation = ConversationId("conversation-2")
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="read-first",
                        name="filesystem_read_file",
                        arguments={"path": str(external_file)},
                    ),
                ),
            ),
            ModelResponse(text="Read the first conversation file.", tool_calls=()),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="read-second",
                        name="filesystem_read_file",
                        arguments={"path": str(external_file)},
                    ),
                ),
            ),
            ModelResponse(
                text="The second conversation cannot read it.", tool_calls=()
            ),
        ),
    )
    workspace_settings = ConversationWorkspaceSettings(
        scopes=scopes,
        workspace_root=paths.workspace_dir,
    )

    try:
        created_at = datetime(2026, 8, 12, 17, 30, tzinfo=UTC)
        for conversation_id in (first_conversation, second_conversation):
            await conversations.save(
                Conversation(
                    conversation_id=conversation_id,
                    user_id=UserId("local-user"),
                    created_at=created_at,
                    updated_at=created_at,
                ),
            )
        await scopes.save(
            ConversationFileScope(
                conversation_id=first_conversation,
                additional_roots=(external_folder.resolve(),),
                additional_files=(external_file.resolve(),),
            ),
        )
        runtime = build_persistent_agent_runtime(
            model=provider,
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            workspace_settings=workspace_settings,
        )

        first = await runtime.run(
            conversation_id=first_conversation,
            content="Read my file.",
            model_name="fake-model",
            system_prompt="Use tools.",
        )
        second = await runtime.run(
            conversation_id=second_conversation,
            content="Read the same file.",
            model_name="fake-model",
            system_prompt="Use tools.",
        )

        assert first.run.status is RunStatus.COMPLETED
        assert second.run.status is RunStatus.COMPLETED
        assert tuple(tool.name for tool in provider.requests[0].tools[-3:]) == (
            "filesystem_list",
            "filesystem_read_file",
            "filesystem_search_files",
        )
        assert "Folder: " + str(external_folder.resolve()) in (
            provider.requests[0].system_prompt
        )
        assert "File: " + str(external_file.resolve()) in (
            provider.requests[0].system_prompt
        )
        assert (
            "attached or shared folders or files"
            in provider.requests[0].system_prompt
        )
        assert str(external_file.resolve()) not in provider.requests[2].system_prompt
        assert provider.requests[1].messages[-1].role is ModelMessageRole.TOOL
        assert provider.requests[1].messages[-1].content == "conversation one only"
        assert provider.requests[3].messages[-1].role is ModelMessageRole.TOOL
        assert (
            provider.requests[3].messages[-1].content == "Error: tool execution failed."
        )
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await scopes.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_runtime_registers_and_executes_reversible_file_write_tools(
    tmp_path: Path,
) -> None:
    paths = AppPaths.from_root(tmp_path / "app-home")
    paths.workspace_dir.mkdir(parents=True)
    database_path = paths.data_dir / "asagent.sqlite3"
    upgrade_sqlite_database(
        database_path=database_path,
        alembic_config_path=_alembic_config_path(),
    )
    conversations = SqliteConversationRepository(database_path)
    scopes = SqliteConversationFileScopeRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    changes = SqliteFileChangeRepository(database_path)
    conversation_id = ConversationId("conversation-write")
    target = paths.workspace_dir / "created.txt"
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="create-file",
                        name="filesystem_create_file",
                        arguments={"path": str(target), "content": "created by agent"},
                    ),
                ),
            ),
            ModelResponse(text="Created the file.", tool_calls=()),
        ),
    )
    now = datetime(2026, 8, 15, 18, 0, tzinfo=UTC)
    try:
        await conversations.save(
            Conversation(conversation_id, UserId("local-user"), now, now)
        )
        runtime = build_persistent_agent_runtime(
            model=provider,
            conversations=conversations,
            runs=runs,
            starter=starter,
            finisher=finisher,
            approval_policy=AllowAllApprovals(),
            workspace_settings=ConversationWorkspaceSettings(
                scopes=scopes,
                workspace_root=paths.workspace_dir,
            ),
            file_changes=changes,
            file_change_snapshots=FileChangeSnapshotStore(paths.data_dir),
        )

        result = await runtime.run(
            conversation_id=conversation_id,
            content="Create created.txt.",
            model_name="fake-model",
            system_prompt="Use tools.",
        )

        assert result.run.status is RunStatus.COMPLETED
        assert target.read_text(encoding="utf-8") == "created by agent"
        recorded = await changes.list_for_run(result.run.run_id)
        assert len(recorded) == 1
        assert str(recorded[0].file_change_id).startswith("change_")
        assert {tool.name for tool in provider.requests[0].tools} >= {
            "filesystem_create_file",
            "filesystem_replace_file",
            "filesystem_delete_file",
        }
    finally:
        await changes.aclose()
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await scopes.aclose()
        await conversations.aclose()
