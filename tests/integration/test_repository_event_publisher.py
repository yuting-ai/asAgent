from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, EventId, RunId, UserId
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.storage.event_publisher import RepositoryEventPublisher
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
async def test_event_publisher_persists_and_replays_events_in_sequence_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    run = _run(RunId("run-1"), conversation_id)
    first_event = RunEvent(
        event_id=EventId("event-1"),
        run_id=run.run_id,
        conversation_id=conversation_id,
        sequence=1,
        event_type="run.started",
        created_at=datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
        data={},
    )
    second_event = RunEvent(
        event_id=EventId("event-2"),
        run_id=run.run_id,
        conversation_id=conversation_id,
        sequence=2,
        event_type="model.completed",
        created_at=datetime(2026, 8, 10, 14, 1, tzinfo=UTC),
        data={"step": 1, "tool_call_count": 0},
    )

    conversations = SqliteConversationRepository(database_path)
    repository = SqliteRunRepository(database_path)
    publisher = RepositoryEventPublisher(repository)

    try:
        await conversations.save(_conversation(conversation_id))
        await repository.save(run)
        await publisher.publish(second_event)
        await publisher.publish(first_event)
    finally:
        await repository.aclose()
        await conversations.aclose()

    reopened = SqliteRunRepository(database_path)
    try:
        assert await reopened.list_events(run.run_id) == (
            first_event,
            second_event,
        )
        assert await reopened.list_events(
            run.run_id,
            after_sequence=1,
        ) == (second_event,)
    finally:
        await reopened.aclose()
