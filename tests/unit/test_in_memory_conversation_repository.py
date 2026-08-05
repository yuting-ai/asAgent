from datetime import UTC, datetime

import pytest

from ragent.core.conversation import Conversation
from ragent.core.ids import ConversationId, MessageId, UserId
from ragent.core.messages import AssistantMessage, UserMessage
from ragent.core.repositories import ConversationRepository
from ragent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


def make_conversation(
    conversation_id: ConversationId,
    user_id: UserId,
    *,
    updated_at: datetime | None = None,
) -> Conversation:
    created_at = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        created_at=created_at,
        updated_at=updated_at or created_at,
    )


@pytest.mark.asyncio
async def test_repository_saves_gets_and_filters_conversations_by_user() -> None:
    repository: ConversationRepository = InMemoryConversationRepository()
    local_user = UserId("local-user")
    other_user = UserId("other-user")
    local_conversation = make_conversation(ConversationId("conv_local"), local_user)
    other_conversation = make_conversation(ConversationId("conv_other"), other_user)

    await repository.save(local_conversation)
    await repository.save(other_conversation)

    assert isinstance(repository, ConversationRepository)
    assert await repository.get(ConversationId("conv_local")) == local_conversation
    assert await repository.get(ConversationId("conv_missing")) is None
    assert await repository.list_for_user(local_user) == (local_conversation,)


@pytest.mark.asyncio
async def test_save_replaces_a_conversation_with_the_same_stable_id() -> None:
    repository = InMemoryConversationRepository()
    conversation_id = ConversationId("conv_123")
    user_id = UserId("local-user")
    original = make_conversation(conversation_id, user_id)
    updated = make_conversation(
        conversation_id,
        user_id,
        updated_at=datetime(2026, 8, 5, 9, 1, tzinfo=UTC),
    )

    await repository.save(original)
    await repository.save(updated)

    assert await repository.get(conversation_id) == updated
    assert await repository.list_for_user(user_id) == (updated,)


@pytest.mark.asyncio
async def test_messages_are_scoped_ordered_and_require_a_saved_conversation() -> None:
    repository = InMemoryConversationRepository()
    conversation_id = ConversationId("conv_123")
    await repository.save(
        make_conversation(conversation_id, UserId("local-user")),
    )

    user_message = UserMessage(
        message_id=MessageId("msg_user_123"),
        conversation_id=conversation_id,
        content="Hello, Ragent.",
        created_at=datetime(2026, 8, 5, 9, 2, tzinfo=UTC),
    )
    assistant_message = AssistantMessage(
        message_id=MessageId("msg_assistant_123"),
        conversation_id=conversation_id,
        content="Hello! How can I help?",
        created_at=datetime(2026, 8, 5, 9, 3, tzinfo=UTC),
    )

    await repository.append_message(user_message)
    await repository.append_message(assistant_message)

    assert await repository.list_messages(conversation_id) == (
        user_message,
        assistant_message,
    )
    assert await repository.list_messages(ConversationId("conv_other")) == ()

    with pytest.raises(ValueError, match="unknown conversation"):
        await repository.append_message(
            UserMessage(
                message_id=MessageId("msg_orphan"),
                conversation_id=ConversationId("conv_missing"),
                content="This should not be saved.",
                created_at=datetime(2026, 8, 5, 9, 4, tzinfo=UTC),
            ),
        )
