from datetime import UTC, datetime

import pytest

from asagent.core.conversation import Conversation
from asagent.core.ids import (
    ConversationId,
    EventId,
    MessageId,
    RunId,
    ToolCallId,
    UserId,
)
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository, RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall


def make_conversation() -> Conversation:
    created_at = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def make_run() -> Run:
    created_at = datetime(2026, 8, 4, 10, 1, tzinfo=UTC)
    return Run(
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        status=RunStatus.CREATED,
        created_at=created_at,
        updated_at=created_at,
    )


class ExampleConversationRepository:
    async def get(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None:
        conversation = make_conversation()
        if conversation.conversation_id == conversation_id:
            return conversation
        return None

    async def list_for_user(self, user_id: UserId) -> tuple[Conversation, ...]:
        conversation = make_conversation()
        if conversation.user_id == user_id:
            return (conversation,)
        return ()

    async def save(self, conversation: Conversation) -> None:
        del conversation

    async def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> tuple[UserMessage | AssistantMessage, ...]:
        if conversation_id != ConversationId("conv_123"):
            return ()

        created_at = datetime(2026, 8, 4, 10, 2, tzinfo=UTC)
        return (
            UserMessage(
                message_id=MessageId("msg_user_123"),
                conversation_id=conversation_id,
                content="Hello, asAgent.",
                created_at=created_at,
            ),
        )

    async def append_message(
        self,
        message: UserMessage | AssistantMessage,
    ) -> None:
        del message

    async def delete(self, conversation_id: ConversationId) -> bool:
        return conversation_id == ConversationId("conv_123")


class ExampleRunRepository:
    async def get(self, run_id: RunId) -> Run | None:
        run = make_run()
        if run.run_id == run_id:
            return run
        return None

    async def list_for_conversation(
        self,
        conversation_id: ConversationId,
    ) -> tuple[Run, ...]:
        run = make_run()
        if run.conversation_id == conversation_id:
            return (run,)
        return ()

    async def save(self, run: Run) -> None:
        del run

    async def append_event(self, event: RunEvent) -> None:
        del event

    async def list_events(
        self,
        run_id: RunId,
        *,
        after_sequence: int = 0,
    ) -> tuple[RunEvent, ...]:
        if run_id != RunId("run_123") or after_sequence >= 1:
            return ()

        return (
            RunEvent(
                event_id=EventId("evt_123"),
                run_id=run_id,
                conversation_id=ConversationId("conv_123"),
                sequence=1,
                event_type="run.started",
                created_at=datetime(2026, 8, 4, 10, 3, tzinfo=UTC),
                data={},
            ),
        )

    async def save_tool_call(self, tool_call: ToolCall) -> None:
        del tool_call

    async def list_tool_calls(
        self,
        run_id: RunId,
    ) -> tuple[ToolCall, ...]:
        if run_id != RunId("run_123"):
            return ()

        return (
            ToolCall(
                tool_call_id=ToolCallId("tool_123"),
                run_id=run_id,
                model_call_id="call_123",
                tool_id="builtin.echo",
                arguments={"text": "Hello, asAgent."},
                result=None,
                error=None,
                created_at=datetime(2026, 8, 4, 10, 4, tzinfo=UTC),
                completed_at=None,
            ),
        )


@pytest.mark.asyncio
async def test_example_conversation_repository_satisfies_protocol() -> None:
    repository: ConversationRepository = ExampleConversationRepository()

    assert isinstance(repository, ConversationRepository)
    assert await repository.get(ConversationId("conv_123")) == make_conversation()
    assert await repository.list_for_user(UserId("local-user")) == (
        make_conversation(),
    )

    messages = await repository.list_messages(ConversationId("conv_123"))
    assert len(messages) == 1
    assert isinstance(messages[0], UserMessage)


@pytest.mark.asyncio
async def test_example_run_repository_satisfies_protocol() -> None:
    repository: RunRepository = ExampleRunRepository()

    assert isinstance(repository, RunRepository)
    assert await repository.get(RunId("run_123")) == make_run()
    assert await repository.list_for_conversation(ConversationId("conv_123")) == (
        make_run(),
    )

    events = await repository.list_events(RunId("run_123"))
    assert [event.sequence for event in events] == [1]
    assert await repository.list_events(RunId("run_123"), after_sequence=1) == ()

    tool_calls = await repository.list_tool_calls(RunId("run_123"))
    assert [tool_call.tool_id for tool_call in tool_calls] == ["builtin.echo"]
