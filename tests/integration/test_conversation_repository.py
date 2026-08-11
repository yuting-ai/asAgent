from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(
    conversation_id: ConversationId,
    user_id: UserId,
    *,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    title: str | None = None,
) -> Conversation:
    creation_time = created_at or datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        created_at=creation_time,
        updated_at=updated_at or creation_time,
        title=title,
    )


@pytest.mark.asyncio
async def test_persists_conversations_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    local_user = UserId("local-user")
    other_user = UserId("other-user")
    local_conversation = _conversation(ConversationId("conversation-local"), local_user)
    other_conversation = _conversation(ConversationId("conversation-other"), other_user)

    repository = SqliteConversationRepository(database_path)
    protocol: ConversationRepository = repository
    assert isinstance(protocol, ConversationRepository)

    await repository.save(local_conversation)
    await repository.save(other_conversation)
    await repository.aclose()

    reopened = SqliteConversationRepository(database_path)
    try:
        assert (
            await reopened.get(local_conversation.conversation_id) == local_conversation
        )
        assert await reopened.get(ConversationId("missing")) is None
        assert await reopened.list_for_user(local_user) == (local_conversation,)
    finally:
        await reopened.aclose()


@pytest.mark.asyncio
async def test_save_replaces_conversation_with_same_stable_id(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    original = _conversation(conversation_id, UserId("local-user"))
    updated = _conversation(
        conversation_id,
        UserId("local-user"),
        updated_at=datetime(2026, 8, 9, 12, 1, tzinfo=UTC),
    )
    repository = SqliteConversationRepository(database_path)

    try:
        await repository.save(original)
        await repository.save(updated)

        assert await repository.get(conversation_id) == updated
    finally:
        await repository.aclose()


@pytest.mark.asyncio
async def test_normalizes_persisted_datetimes_to_utc(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    local_time = datetime(
        2026,
        8,
        9,
        20,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    conversation = _conversation(
        ConversationId("conversation-utc"),
        UserId("local-user"),
        created_at=local_time,
    )
    repository = SqliteConversationRepository(database_path)

    try:
        await repository.save(conversation)

        assert await repository.get(conversation.conversation_id) == _conversation(
            conversation.conversation_id,
            conversation.user_id,
            created_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        )
    finally:
        await repository.aclose()


@pytest.mark.asyncio
async def test_persists_optional_conversation_titles_across_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    titled = _conversation(
        ConversationId("conversation-titled"),
        UserId("local-user"),
        title="Plan the week",
    )
    untitled = _conversation(
        ConversationId("conversation-untitled"),
        UserId("local-user"),
    )
    repository = SqliteConversationRepository(database_path)

    try:
        await repository.save(titled)
        await repository.save(untitled)
    finally:
        await repository.aclose()

    reopened = SqliteConversationRepository(database_path)
    try:
        assert await reopened.get(titled.conversation_id) == titled
        assert await reopened.get(untitled.conversation_id) == untitled
        stored_untitled = await reopened.get(untitled.conversation_id)
        assert stored_untitled is not None
        assert stored_untitled.title is None
    finally:
        await reopened.aclose()


@pytest.mark.asyncio
async def test_messages_are_scoped_ordered_and_require_conversation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    repository = SqliteConversationRepository(database_path)
    user_message = UserMessage(
        message_id=MessageId("message-user"),
        conversation_id=conversation_id,
        content="Hello, asAgent.",
        created_at=datetime(2026, 8, 9, 12, 2, tzinfo=UTC),
    )
    assistant_message = AssistantMessage(
        message_id=MessageId("message-assistant"),
        conversation_id=conversation_id,
        content="Hello! How can I help?",
        created_at=datetime(2026, 8, 9, 12, 1, tzinfo=UTC),
    )

    try:
        await repository.save(
            _conversation(conversation_id, UserId("local-user")),
        )
        await repository.append_message(user_message)
        await repository.append_message(assistant_message)

        assert await repository.list_messages(conversation_id) == (
            user_message,
            assistant_message,
        )
        assert await repository.list_messages(ConversationId("missing")) == ()

        with pytest.raises(ValueError, match="unknown conversation"):
            await repository.append_message(
                UserMessage(
                    message_id=MessageId("message-orphan"),
                    conversation_id=ConversationId("missing"),
                    content="not saved",
                    created_at=datetime(2026, 8, 9, 12, 3, tzinfo=UTC),
                ),
            )
    finally:
        await repository.aclose()
