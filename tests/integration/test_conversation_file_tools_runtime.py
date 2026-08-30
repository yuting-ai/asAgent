import io
import json
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pypdf
import pytest
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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
        assert tuple(tool.name for tool in provider.requests[0].tools[-4:]) == (
            "filesystem_list",
            "filesystem_read_file",
            "document_extract_text",
            "filesystem_search_files",
        )
        assert "Folder: " + str(external_folder.resolve()) in (
            provider.requests[0].system_prompt
        )
        assert "File: " + str(external_file.resolve()) in (
            provider.requests[0].system_prompt
        )
        assert (
            "attached or shared folders or files" in provider.requests[0].system_prompt
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


def _make_pdf(pages_text: list[str]) -> bytes:
    writer = pypdf.PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in pages_text:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font,
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        escaped_text = (
            text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        stream.set_data(
            f"BT /F1 12 Tf 50 250 Td ({escaped_text}) Tj ET".encode(
                "latin1", errors="replace"
            )
        )
        page[NameObject("/Contents")] = stream

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_runtime_extracts_pdf_text_end_to_end(
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
    conversation_id = ConversationId("conversation-pdf")

    pdf_bytes = _make_pdf(
        [
            "Page 1 Overview",
            "Page 2 Financial Summary",
            "Page 3 Appendix",
        ]
    )
    pdf_path = paths.workspace_dir / "report.pdf"
    pdf_path.write_bytes(pdf_bytes)

    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="extract-pdf-1",
                        name="document_extract_text",
                        arguments={
                            "path": str(pdf_path),
                            "start_page": 2,
                            "end_page": 2,
                        },
                    ),
                ),
            ),
            ModelResponse(text="Page 2 contains Financial Summary.", tool_calls=()),
        ),
    )
    now = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)

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
            workspace_settings=ConversationWorkspaceSettings(
                scopes=scopes,
                workspace_root=paths.workspace_dir,
            ),
        )

        result = await runtime.run(
            conversation_id=conversation_id,
            content="Extract page 2 from report.pdf.",
            model_name="fake-model",
            system_prompt="Use tools.",
        )

        assert result.run.status is RunStatus.COMPLETED
        assert result.assistant_message is not None
        assert result.assistant_message.content == "Page 2 contains Financial Summary."

        # Verify tool call recorded in SQLite
        tool_calls = await runs.list_tool_calls(result.run.run_id)
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_id == "document.extract_text"
        assert tool_calls[0].model_call_id == "extract-pdf-1"
        assert tool_calls[0].error is None
        assert tool_calls[0].result is not None
        parsed_result = json.loads(tool_calls[0].result)
        assert parsed_result["format"] == "pdf"
        assert parsed_result["page_count"] == 3
        assert parsed_result["start_page"] == 2
        assert parsed_result["start_char_offset"] == 0
        assert parsed_result["end_page"] == 2
        assert parsed_result["pages"][0]["text"] == "Page 2 Financial Summary"
        assert parsed_result["next_position"] == {"page": 3, "char_offset": 0}
        assert parsed_result["text_layer_found"] is True
        assert parsed_result["truncated"] is False

        # Verify events: no approval requested event
        events = await runs.list_events(result.run.run_id)
        event_types = [e.event_type for e in events]
        assert "tool.approval_requested" not in event_types
        assert "tool.requested" in event_types
        assert "tool.completed" in event_types
        assert "run.completed" in event_types

        # Verify model message history pairing
        assert provider.requests[1].messages[-1].role is ModelMessageRole.TOOL
        assert provider.requests[1].messages[-1].tool_call_id == "extract-pdf-1"

        # Verify original PDF file was not modified
        assert pdf_path.read_bytes() == pdf_bytes

        # Verify no extra files created in workspace
        assert list(paths.workspace_dir.iterdir()) == [pdf_path]

        # Verify SQLite tables contain only expected system tables
        async with aiosqlite.connect(database_path) as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ) as cursor:
                tables = [row[0] for row in await cursor.fetchall()]
        assert "document_extract_text" not in tables
        assert "pdf_extracts" not in tables
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await scopes.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_runtime_handles_pdf_errors_and_maintains_next_run(
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
    conversation_id = ConversationId("conversation-pdf-err")

    corrupted_pdf = paths.workspace_dir / "corrupted.pdf"
    corrupted_pdf.write_bytes(b"%PDF-broken-stream")

    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="extract-broken",
                        name="document_extract_text",
                        arguments={"path": str(corrupted_pdf)},
                    ),
                ),
            ),
            ModelResponse(text="The PDF is corrupted.", tool_calls=()),
            # Next Run responses:
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call-time",
                        name="builtin_current_time",
                        arguments={},
                    ),
                ),
            ),
            ModelResponse(text="It is now UTC time.", tool_calls=()),
        ),
    )
    now = datetime(2026, 8, 30, 10, 30, tzinfo=UTC)

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
            workspace_settings=ConversationWorkspaceSettings(
                scopes=scopes,
                workspace_root=paths.workspace_dir,
            ),
        )

        # Run 1: Fails tool execution cleanly and returns text
        first = await runtime.run(
            conversation_id=conversation_id,
            content="Extract corrupted.pdf.",
            model_name="fake-model",
            system_prompt="Use tools.",
        )

        assert first.run.status is RunStatus.COMPLETED
        assert first.assistant_message is not None
        assert first.assistant_message.content == "The PDF is corrupted."
        assert provider.requests[1].messages[-1].role is ModelMessageRole.TOOL
        assert (
            provider.requests[1].messages[-1].content == "Error: tool execution failed."
        )

        # Run 2: Next run in the same conversation succeeds without issue
        second = await runtime.run(
            conversation_id=conversation_id,
            content="What time is it?",
            model_name="fake-model",
            system_prompt="Use tools.",
        )

        assert second.run.status is RunStatus.COMPLETED
        assert second.assistant_message is not None
        assert second.assistant_message.content == "It is now UTC time."
    finally:
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await scopes.aclose()
        await conversations.aclose()
