from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from ragent.chat.service import ChatService
from ragent.core.conversation import Conversation
from ragent.core.ids import ConversationId, MessageId, UserId
from ragent.core.messages import UserMessage
from ragent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelResponse,
    ModelToolCall,
)
from ragent.models.fake_provider import FakeModelProvider
from ragent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


def make_conversation() -> Conversation:
    created_at = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def make_chat_service(
    *,
    repository: InMemoryConversationRepository,
    provider: FakeModelProvider,
    timestamps: Iterator[datetime],
    message_ids: Iterator[MessageId],
) -> ChatService:
    def now() -> datetime:
        return next(timestamps)

    def new_message_id() -> MessageId:
        return next(message_ids)

    return ChatService(
        conversations=repository,
        model_provider=provider,
        now=now,
        new_message_id=new_message_id,
    )


@pytest.mark.asyncio
async def test_send_persists_messages_and_uses_conversation_history() -> None:
    repository = InMemoryConversationRepository()
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text="Hello!", tool_calls=()),
            ModelResponse(text="I am Ragent.", tool_calls=()),
        ),
    )
    service = make_chat_service(
        repository=repository,
        provider=provider,
        timestamps=iter(
            (
                datetime(2026, 8, 5, 10, 1, tzinfo=UTC),
                datetime(2026, 8, 5, 10, 2, tzinfo=UTC),
                datetime(2026, 8, 5, 10, 3, tzinfo=UTC),
                datetime(2026, 8, 5, 10, 4, tzinfo=UTC),
            ),
        ),
        message_ids=iter(
            (
                MessageId("msg_user_1"),
                MessageId("msg_assistant_1"),
                MessageId("msg_user_2"),
                MessageId("msg_assistant_2"),
            ),
        ),
    )
    conversation = make_conversation()

    first_reply = await service.send(
        conversation=conversation,
        content="Hello, Ragent.",
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
    )
    second_reply = await service.send(
        conversation=conversation,
        content="Who are you?",
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
    )

    assert first_reply.content == "Hello!"
    assert second_reply.content == "I am Ragent."
    assert [
        message.content
        for message in await repository.list_messages(
            conversation.conversation_id,
        )
    ] == [
        "Hello, Ragent.",
        "Hello!",
        "Who are you?",
        "I am Ragent.",
    ]
    assert provider.requests[1].messages == (
        ModelMessage(
            role=ModelMessageRole.USER,
            content="Hello, Ragent.",
        ),
        ModelMessage(
            role=ModelMessageRole.ASSISTANT,
            content="Hello!",
        ),
        ModelMessage(
            role=ModelMessageRole.USER,
            content="Who are you?",
        ),
    )


@pytest.mark.asyncio
async def test_send_preserves_user_message_when_provider_fails() -> None:
    repository = InMemoryConversationRepository()
    service = make_chat_service(
        repository=repository,
        provider=FakeModelProvider(),
        timestamps=iter((datetime(2026, 8, 5, 10, 1, tzinfo=UTC),)),
        message_ids=iter((MessageId("msg_user_1"),)),
    )
    conversation = make_conversation()

    with pytest.raises(RuntimeError, match="no scripted response"):
        await service.send(
            conversation=conversation,
            content="Hello, Ragent.",
            model_name="fake-model",
            system_prompt="You are a helpful assistant.",
        )

    assert await repository.list_messages(conversation.conversation_id) == (
        UserMessage(
            message_id=MessageId("msg_user_1"),
            conversation_id=conversation.conversation_id,
            content="Hello, Ragent.",
            created_at=datetime(2026, 8, 5, 10, 1, tzinfo=UTC),
        ),
    )


@pytest.mark.asyncio
async def test_send_rejects_tool_calls_before_agent_loop_exists() -> None:
    repository = InMemoryConversationRepository()
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="builtin.echo",
                        arguments={"text": "Hello"},
                    ),
                ),
            ),
        ),
    )
    service = make_chat_service(
        repository=repository,
        provider=provider,
        timestamps=iter((datetime(2026, 8, 5, 10, 1, tzinfo=UTC),)),
        message_ids=iter((MessageId("msg_user_1"),)),
    )

    with pytest.raises(ValueError, match="text response without tool calls"):
        await service.send(
            conversation=make_conversation(),
            content="Use a tool.",
            model_name="fake-model",
            system_prompt="You are a helpful assistant.",
        )
