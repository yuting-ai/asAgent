from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.file_change import FileChange, FileChangeOperation, FileChangeStatus
from asagent.core.ids import ConversationId, FileChangeId, RunId, UserId
from asagent.core.repositories import FileChangeRepository
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import SqliteConversationRepository
from asagent.storage.sqlite.file_change_repository import SqliteFileChangeRepository
from asagent.storage.sqlite.run_repository import SqliteRunRepository


def _upgrade(path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_persists_file_changes_across_instances_and_orders_by_run(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    conversation_id = ConversationId("conversation-1")
    run_id = RunId("run-1")
    now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    repository = SqliteFileChangeRepository(database_path)
    protocol: FileChangeRepository = repository
    change = FileChange(
        FileChangeId("change-1"),
        run_id,
        FileChangeOperation.REPLACE,
        FileChangeStatus.PREPARED,
        "/workspace",
        "notes.txt",
        "before",
        "after",
        "file-changes/change-1.before",
        now,
        now,
    )
    updated = FileChange(
        change.file_change_id,
        run_id,
        change.operation,
        FileChangeStatus.APPLIED,
        change.root_path,
        change.relative_path,
        change.before_hash,
        change.after_hash,
        change.snapshot_ref,
        now,
        datetime(2026, 8, 15, 12, 1, tzinfo=UTC),
    )
    try:
        assert isinstance(protocol, FileChangeRepository)
        await conversations.save(
            Conversation(conversation_id, UserId("local-user"), now, now)
        )
        await runs.save(Run(run_id, conversation_id, RunStatus.CREATED, now, now))
        await repository.save(change)
        await repository.save(updated)
        assert await repository.get(change.file_change_id) == updated
        assert await repository.get(FileChangeId("missing")) is None
        assert await repository.list_for_run(run_id) == (updated,)
        assert await repository.list_for_run(RunId("missing")) == ()
    finally:
        await repository.aclose()
        await runs.aclose()
        await conversations.aclose()
