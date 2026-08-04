from typing import Protocol, runtime_checkable

from ragent.core.conversation import Conversation
from ragent.core.ids import ConversationId, RunId, UserId
from ragent.core.messages import AssistantMessage, UserMessage
from ragent.core.run import Run
from ragent.core.run_event import RunEvent
from ragent.core.tool_call import ToolCall


@runtime_checkable
class ConversationRepository(Protocol):
    async def get(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None: ...

    async def list_for_user(self, user_id: UserId) -> tuple[Conversation, ...]: ...

    async def save(self, conversation: Conversation) -> None: ...

    async def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> tuple[UserMessage | AssistantMessage, ...]: ...

    async def append_message(
        self,
        message: UserMessage | AssistantMessage,
    ) -> None: ...


@runtime_checkable
class RunRepository(Protocol):
    async def get(self, run_id: RunId) -> Run | None: ...

    async def list_for_conversation(
        self,
        conversation_id: ConversationId,
    ) -> tuple[Run, ...]: ...

    async def save(self, run: Run) -> None: ...

    async def append_event(self, event: RunEvent) -> None: ...

    async def list_events(
        self,
        run_id: RunId,
        *,
        after_sequence: int = 0,
    ) -> tuple[RunEvent, ...]: ...

    async def save_tool_call(self, tool_call: ToolCall) -> None: ...

    async def list_tool_calls(self, run_id: RunId) -> tuple[ToolCall, ...]: ...
