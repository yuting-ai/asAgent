from typing import Protocol, runtime_checkable

from asagent.core.connection import Connection
from asagent.core.conversation import Conversation
from asagent.core.ids import ConnectionId, ConversationId, RunId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.tool_call import ToolCall


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


@runtime_checkable
class ConnectionRepository(Protocol):
    async def get(
        self,
        connection_id: ConnectionId,
    ) -> Connection | None: ...

    async def list_for_user(self, user_id: UserId) -> tuple[Connection, ...]: ...

    async def save(self, connection: Connection) -> None: ...

    async def delete(self, connection_id: ConnectionId) -> bool: ...
