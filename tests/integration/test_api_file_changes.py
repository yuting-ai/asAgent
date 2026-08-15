from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.run_submission import RunSubmissionService
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.file_change import FileChange
from asagent.core.ids import ConversationId, FileChangeId, MessageId, RunId, UserId
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.reversible_files import ReversibleFileService
from asagent.storage.sqlite.conversation_repository import SqliteConversationRepository
from asagent.storage.sqlite.file_change_repository import SqliteFileChangeRepository
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.workspace.resolver import WorkspaceResolver


def _upgrade(path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_local_api_lists_and_manually_undoes_conversation_file_change(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "notes.txt"
    target.write_text("before", encoding="utf-8")
    now = datetime(2026, 8, 15, 15, 0, tzinfo=UTC)
    conversation_id = ConversationId("conversation-1")
    run_id = RunId("run-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    changes = SqliteFileChangeRepository(database_path)
    service = ReversibleFileService(
        WorkspaceResolver(workspace_root=workspace),
        changes,
        FileChangeSnapshotStore(tmp_path / "data"),
        lambda: FileChangeId("change-1"),
        lambda: now,
    )
    submission = RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=lambda: now,
        new_run_id=lambda: RunId("unused-run"),
        new_message_id=lambda: MessageId("unused-message"),
    )

    async def revert(change_id: FileChangeId, path: Path) -> FileChange:
        return await service.revert(change_id, expected_path=path)

    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=submission,
        dispatch_submitted_run=lambda _: None,
        cancel_run=lambda _: False,
        file_changes=changes,
        revert_file_change=revert,
    )
    headers = {"Authorization": "Bearer test-token"}
    try:
        await conversations.save(
            Conversation(conversation_id, UserId("local-user"), now, now)
        )
        await runs.save(Run(run_id, conversation_id, RunStatus.COMPLETED, now, now))
        await service.replace_text(run_id=run_id, path=target, content="after")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            listed = await client.get(
                f"/api/v1/conversations/{conversation_id}/file-changes",
                headers=headers,
            )
            rejected = await client.post(
                "/api/v1/file-changes/change-1/undo",
                headers=headers,
                json={"path": str(workspace / "wrong.txt")},
            )
            undone = await client.post(
                "/api/v1/file-changes/change-1/undo",
                headers=headers,
                json={"path": str(target)},
            )

        assert listed.status_code == 200
        assert listed.json()[0] | {"created_at": None, "updated_at": None} == {
            "change_id": "change-1",
            "run_id": "run-1",
            "operation": "replace",
            "status": "applied",
            "path": str(target),
            "created_at": None,
            "updated_at": None,
        }
        assert rejected.status_code == 409
        assert target.read_text(encoding="utf-8") == "before"
        assert undone.status_code == 200
        assert undone.json()["status"] == "reverted"
    finally:
        await changes.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
