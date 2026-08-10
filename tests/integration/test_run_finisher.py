from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import AssistantMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(conversation_id: ConversationId) -> Conversation:
    created_at = datetime(2026, 8, 10, 16, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def _run(
    conversation_id: ConversationId,
    run_id: str,
    *,
    status: RunStatus = RunStatus.CREATED,
    updated_at: datetime | None = None,
) -> Run:
    created_at = datetime(2026, 8, 10, 16, 1, tzinfo=UTC)
    return Run(
        run_id=RunId(run_id),
        conversation_id=conversation_id,
        status=status,
        created_at=created_at,
        updated_at=updated_at or created_at,
    )


def _assistant_message(
    conversation_id: ConversationId,
    message_id: str,
) -> AssistantMessage:
    return AssistantMessage(
        message_id=MessageId(message_id),
        conversation_id=conversation_id,
        content="The task is complete.",
        created_at=datetime(2026, 8, 10, 16, 2, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_finishes_run_and_appends_assistant_message_atomically(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    initial_run = _run(conversation_id, "run-1")
    finished_run = _run(
        conversation_id,
        "run-1",
        status=RunStatus.COMPLETED,
        updated_at=datetime(2026, 8, 10, 16, 2, tzinfo=UTC),
    )
    assistant_message = _assistant_message(conversation_id, "message-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await runs.save(initial_run)

        await finisher.finish(
            run=finished_run,
            assistant_message=assistant_message,
        )

        assert await runs.get(finished_run.run_id) == finished_run
        assert await conversations.list_messages(conversation_id) == (
            assistant_message,
        )
    finally:
        await finisher.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_finishes_failed_run_without_assistant_message(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    initial_run = _run(conversation_id, "run-1")
    failed_run = _run(
        conversation_id,
        "run-1",
        status=RunStatus.FAILED,
        updated_at=datetime(2026, 8, 10, 16, 2, tzinfo=UTC),
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await runs.save(initial_run)

        await finisher.finish(run=failed_run, assistant_message=None)

        assert await runs.get(failed_run.run_id) == failed_run
        assert await conversations.list_messages(conversation_id) == ()
    finally:
        await finisher.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rejects_mismatched_assistant_message_without_writing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    other_conversation_id = ConversationId("conversation-2")
    initial_run = _run(conversation_id, "run-1")
    finished_run = _run(
        conversation_id,
        "run-1",
        status=RunStatus.COMPLETED,
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await conversations.save(_conversation(other_conversation_id))
        await runs.save(initial_run)

        with pytest.raises(ValueError, match="same conversation"):
            await finisher.finish(
                run=finished_run,
                assistant_message=_assistant_message(
                    other_conversation_id,
                    "message-1",
                ),
            )

        assert await runs.get(initial_run.run_id) == initial_run
        assert await conversations.list_messages(conversation_id) == ()
    finally:
        await finisher.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rolls_back_run_update_when_assistant_message_insert_fails(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    initial_run = _run(conversation_id, "run-1")
    finished_run = _run(
        conversation_id,
        "run-1",
        status=RunStatus.COMPLETED,
        updated_at=datetime(2026, 8, 10, 16, 2, tzinfo=UTC),
    )
    existing_message = _assistant_message(conversation_id, "message-1")
    duplicate_message = _assistant_message(conversation_id, "message-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    finisher = SqliteRunFinisher(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await conversations.append_message(existing_message)
        await runs.save(initial_run)

        with pytest.raises(IntegrityError):
            await finisher.finish(
                run=finished_run,
                assistant_message=duplicate_message,
            )

        assert await runs.get(initial_run.run_id) == initial_run
        assert await conversations.list_messages(conversation_id) == (existing_message,)
    finally:
        await finisher.aclose()
        await runs.aclose()
        await conversations.aclose()
