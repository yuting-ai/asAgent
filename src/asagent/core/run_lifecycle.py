from typing import Protocol, runtime_checkable

from asagent.core.conversation import Conversation
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.run import Run


@runtime_checkable
class RunStarter(Protocol):
    async def start(
        self,
        *,
        conversation: Conversation,
        user_message: UserMessage,
        run: Run,
    ) -> None: ...


@runtime_checkable
class RunFinisher(Protocol):
    async def finish(
        self,
        *,
        run: Run,
        assistant_message: AssistantMessage | None,
    ) -> None: ...
