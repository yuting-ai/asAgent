from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from asagent.chat.service import ChatService
from asagent.cli import run_chat
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, UserId
from asagent.models.contracts import ModelResponse
from asagent.models.fake_provider import FakeModelProvider
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)


def make_conversation() -> Conversation:
    created_at = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
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
async def test_cli_runs_multiple_turns_until_exit() -> None:
    repository = InMemoryConversationRepository()
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text="Hello!", tool_calls=()),
            ModelResponse(text="I am asAgent.", tool_calls=()),
        ),
    )
    chat_service = make_chat_service(
        repository=repository,
        provider=provider,
        timestamps=iter(
            (
                datetime(2026, 8, 6, 9, 1, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 2, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 3, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 4, tzinfo=UTC),
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
    inputs = iter(("Hello, asAgent.", "Who are you?", "exit"))
    output: list[str] = []

    def read_line(prompt: str) -> str:
        assert prompt == "You: "
        return next(inputs)

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=read_line,
        write_line=output.append,
    )

    assert output == [
        "asAgent development chat. Type 'exit' to quit.",
        "asAgent: Hello!",
        "asAgent: I am asAgent.",
    ]
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_cli_reports_provider_errors_and_returns_to_input() -> None:
    repository = InMemoryConversationRepository()
    chat_service = make_chat_service(
        repository=repository,
        provider=FakeModelProvider(),
        timestamps=iter((datetime(2026, 8, 6, 9, 1, tzinfo=UTC),)),
        message_ids=iter((MessageId("msg_user_1"),)),
    )
    output: list[str] = []
    inputs = iter(("Hello, asAgent.", "exit"))

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=lambda _: next(inputs),
        write_line=output.append,
    )

    assert output == [
        "asAgent development chat. Type 'exit' to quit.",
        "Error: no scripted response available",
    ]


@pytest.mark.asyncio
async def test_cli_stops_cleanly_on_end_of_input() -> None:
    repository = InMemoryConversationRepository()
    chat_service = make_chat_service(
        repository=repository,
        provider=FakeModelProvider(),
        timestamps=iter(()),
        message_ids=iter(()),
    )
    output: list[str] = []

    def read_line(_: str) -> str:
        raise EOFError

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=read_line,
        write_line=output.append,
    )

    assert output == ["asAgent development chat. Type 'exit' to quit."]
