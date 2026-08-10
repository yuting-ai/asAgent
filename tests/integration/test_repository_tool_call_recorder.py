from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, RunId, ToolCallId, UserId
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.tool_call_recorder import RepositoryToolCallRecorder


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(conversation_id: ConversationId) -> Conversation:
    created_at = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def _run(run_id: RunId, conversation_id: ConversationId) -> Run:
    created_at = datetime(2026, 8, 10, 12, 1, tzinfo=UTC)
    return Run(
        run_id=run_id,
        conversation_id=conversation_id,
        status=RunStatus.CREATED,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_tool_call_recorder_persists_tool_calls_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    run = _run(RunId("run-1"), conversation_id)
    successful_call = ToolCall(
        tool_call_id=ToolCallId("tool-success"),
        run_id=run.run_id,
        model_call_id="model-call-success",
        tool_id="builtin.calculator",
        arguments={"expression": "123 * 456"},
        result="56088",
        error=None,
        created_at=datetime(2026, 8, 10, 15, 0, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 15, 0, 1, tzinfo=UTC),
    )
    failed_call = ToolCall(
        tool_call_id=ToolCallId("tool-failed"),
        run_id=run.run_id,
        model_call_id="model-call-failed",
        tool_id="builtin.echo",
        arguments={"text": "hello"},
        result=None,
        error="Error: tool execution timed out.",
        created_at=datetime(2026, 8, 10, 15, 1, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 15, 1, 1, tzinfo=UTC),
    )

    conversations = SqliteConversationRepository(database_path)
    repository = SqliteRunRepository(database_path)
    recorder = RepositoryToolCallRecorder(repository)

    try:
        await conversations.save(_conversation(conversation_id))
        await repository.save(run)

        await recorder.record(failed_call)
        await recorder.record(successful_call)
    finally:
        await repository.aclose()
        await conversations.aclose()

    reopened = SqliteRunRepository(database_path)
    try:
        assert await reopened.list_tool_calls(run.run_id) == (
            successful_call,
            failed_call,
        )
    finally:
        await reopened.aclose()
