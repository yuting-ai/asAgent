from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, EventId, RunId, ToolCallId, UserId
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository


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


def _run(
    run_id: RunId,
    conversation_id: ConversationId,
    *,
    status: RunStatus = RunStatus.CREATED,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Run:
    creation_time = created_at or datetime(2026, 8, 10, 12, 1, tzinfo=UTC)
    return Run(
        run_id=run_id,
        conversation_id=conversation_id,
        status=status,
        created_at=creation_time,
        updated_at=updated_at or creation_time,
    )


@pytest.mark.asyncio
async def test_persists_runs_across_instances_orders_and_normalizes_utc(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    repository = SqliteRunRepository(database_path)
    protocol: RunRepository = repository
    assert isinstance(protocol, RunRepository)

    earlier = _run(
        RunId("run-earlier"),
        conversation_id,
        created_at=datetime(
            2026,
            8,
            10,
            20,
            1,
            tzinfo=timezone(timedelta(hours=8)),
        ),
    )
    later = _run(
        RunId("run-later"),
        conversation_id,
        created_at=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    updated_later = _run(
        later.run_id,
        conversation_id,
        status=RunStatus.COMPLETED,
        created_at=later.created_at,
        updated_at=datetime(2026, 8, 10, 12, 3, tzinfo=UTC),
    )

    try:
        await conversations.save(_conversation(conversation_id))
        await repository.save(later)
        await repository.save(earlier)
        await repository.save(updated_later)
        await repository.aclose()
        await conversations.aclose()

        reopened = SqliteRunRepository(database_path)
        try:
            assert await reopened.get(earlier.run_id) == _run(
                earlier.run_id,
                conversation_id,
                created_at=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
            )
            assert await reopened.get(later.run_id) == updated_later
            assert await reopened.get(RunId("missing")) is None
            assert await reopened.list_for_conversation(conversation_id) == (
                _run(
                    earlier.run_id,
                    conversation_id,
                    created_at=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
                ),
                updated_later,
            )
        finally:
            await reopened.aclose()
    finally:
        await repository.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_events_are_scoped_ordered_and_support_replay(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    repository = SqliteRunRepository(database_path)
    run = _run(RunId("run-1"), conversation_id)
    second_event = RunEvent(
        event_id=EventId("event-2"),
        run_id=run.run_id,
        conversation_id=conversation_id,
        sequence=2,
        event_type="model.completed",
        created_at=datetime(2026, 8, 10, 12, 3, tzinfo=UTC),
        data={"step": 1, "tool_call_count": 0},
    )
    first_event = RunEvent(
        event_id=EventId("event-1"),
        run_id=run.run_id,
        conversation_id=conversation_id,
        sequence=1,
        event_type="run.started",
        created_at=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        data={},
    )

    try:
        await conversations.save(_conversation(conversation_id))
        await repository.save(run)
        await repository.append_event(second_event)
        await repository.append_event(first_event)

        assert await repository.list_events(run.run_id) == (
            first_event,
            second_event,
        )
        assert await repository.list_events(
            run.run_id,
            after_sequence=1,
        ) == (second_event,)
        assert await repository.list_events(RunId("missing")) == ()

        with pytest.raises(ValueError, match="does not match"):
            await repository.append_event(
                RunEvent(
                    event_id=EventId("event-wrong-conversation"),
                    run_id=run.run_id,
                    conversation_id=ConversationId("conversation-other"),
                    sequence=3,
                    event_type="run.failed",
                    created_at=datetime(2026, 8, 10, 12, 4, tzinfo=UTC),
                    data={},
                ),
            )

        with pytest.raises(ValueError, match="unknown run"):
            await repository.append_event(
                RunEvent(
                    event_id=EventId("event-orphan"),
                    run_id=RunId("missing"),
                    conversation_id=conversation_id,
                    sequence=1,
                    event_type="run.started",
                    created_at=datetime(2026, 8, 10, 12, 4, tzinfo=UTC),
                    data={},
                ),
            )
    finally:
        await repository.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_tool_calls_preserve_results_errors_arguments_and_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversations = SqliteConversationRepository(database_path)
    repository = SqliteRunRepository(database_path)
    run = _run(RunId("run-1"), conversation_id)
    successful_call = ToolCall(
        tool_call_id=ToolCallId("tool-success"),
        run_id=run.run_id,
        model_call_id="model-call-success",
        tool_id="builtin.calculator",
        arguments={"expression": "123 * 456"},
        result="56088",
        error=None,
        created_at=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 12, 2, 1, tzinfo=UTC),
    )
    failed_call = ToolCall(
        tool_call_id=ToolCallId("tool-failed"),
        run_id=run.run_id,
        model_call_id="model-call-failed",
        tool_id="builtin.echo",
        arguments={"text": "hello"},
        result=None,
        error="Error: tool execution timed out.",
        created_at=datetime(2026, 8, 10, 12, 3, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 12, 3, 1, tzinfo=UTC),
    )

    try:
        await conversations.save(_conversation(conversation_id))
        await repository.save(run)
        await repository.save_tool_call(failed_call)
        await repository.save_tool_call(successful_call)

        assert await repository.list_tool_calls(run.run_id) == (
            successful_call,
            failed_call,
        )
        assert await repository.list_tool_calls(RunId("missing")) == ()
    finally:
        await repository.aclose()
        await conversations.aclose()
