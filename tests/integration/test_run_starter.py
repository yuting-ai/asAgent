from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.exc import IntegrityError

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(
    conversation_id: ConversationId,
    *,
    title: str | None = None,
    updated_at: datetime | None = None,
) -> Conversation:
    created_at = datetime(2026, 8, 10, 13, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=updated_at or created_at,
        title=title,
    )


def _user_message(conversation_id: ConversationId, message_id: str) -> UserMessage:
    return UserMessage(
        message_id=MessageId(message_id),
        conversation_id=conversation_id,
        content="Please help me plan today.",
        created_at=datetime(2026, 8, 10, 13, 1, tzinfo=UTC),
    )


def _run(conversation_id: ConversationId, run_id: str) -> Run:
    created_at = datetime(2026, 8, 10, 13, 1, tzinfo=UTC)
    return Run(
        run_id=RunId(run_id),
        conversation_id=conversation_id,
        status=RunStatus.CREATED,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.asyncio
async def test_starts_user_message_and_run_in_one_transaction(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    conversation = _conversation(conversation_id)
    message = _user_message(conversation_id, "message-1")
    run = _run(conversation_id, "run-1")
    updated_conversation = _conversation(
        conversation_id,
        title="Please help me plan today.",
        updated_at=message.created_at,
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)

    try:
        await conversations.save(conversation)
        await starter.start(
            conversation=updated_conversation,
            user_message=message,
            run=run,
        )

        assert await conversations.get(conversation_id) == updated_conversation
        assert await conversations.list_messages(conversation_id) == (message,)
        assert await runs.get(run.run_id) == run
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rejects_mismatched_conversation_without_writing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    other_conversation_id = ConversationId("conversation-2")
    message = _user_message(conversation_id, "message-1")
    run = _run(other_conversation_id, "run-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await conversations.save(_conversation(other_conversation_id))

        with pytest.raises(ValueError, match="belong together"):
            await starter.start(
                conversation=_conversation(conversation_id),
                user_message=message,
                run=run,
            )

        assert await conversations.list_messages(conversation_id) == ()
        assert await runs.get(run.run_id) is None
        stored = await conversations.get(conversation_id)
        assert stored is not None
        assert stored.title is None
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rolls_back_message_when_run_insert_fails(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    existing_run = _run(conversation_id, "run-existing")
    message = _user_message(conversation_id, "message-1")
    duplicate_run = _run(conversation_id, "run-existing")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)

    try:
        await conversations.save(_conversation(conversation_id))
        await runs.save(existing_run)

        with pytest.raises(IntegrityError):
            await starter.start(
                conversation=_conversation(
                    conversation_id,
                    title="Please help me plan today.",
                    updated_at=message.created_at,
                ),
                user_message=message,
                run=duplicate_run,
            )

        assert await conversations.list_messages(conversation_id) == ()
        assert await runs.get(existing_run.run_id) == existing_run
        stored = await conversations.get(conversation_id)
        assert stored is not None
        assert stored.title is None
        assert stored.updated_at == datetime(
            2026,
            8,
            10,
            13,
            0,
            tzinfo=UTC,
        )
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()


@pytest.mark.asyncio
async def test_rejects_unknown_conversation_without_writing(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("missing-conversation")
    message = _user_message(conversation_id, "message-1")
    run = _run(conversation_id, "run-1")
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)

    try:
        with pytest.raises(ValueError, match="unknown conversation"):
            await starter.start(
                conversation=_conversation(conversation_id),
                user_message=message,
                run=run,
            )

        assert await conversations.list_messages(conversation_id) == ()
        assert await runs.get(run.run_id) is None
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
