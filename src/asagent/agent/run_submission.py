from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.repositories import ConversationRepository
from asagent.core.run import Run
from asagent.core.run_lifecycle import RunStarter
from asagent.core.run_status import RunStatus


class UnknownConversationError(ValueError):
    pass


class ConversationAccessDeniedError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SubmittedRun:
    user_message: UserMessage
    run: Run


class RunSubmissionService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        run_starter: RunStarter,
        now: Callable[[], datetime],
        new_run_id: Callable[[], RunId],
        new_message_id: Callable[[], MessageId],
    ) -> None:
        self._conversations = conversations
        self._run_starter = run_starter
        self._now = now
        self._new_run_id = new_run_id
        self._new_message_id = new_message_id

    async def submit(
        self,
        *,
        conversation_id: ConversationId,
        content: str,
        user_id: UserId | None = None,
    ) -> SubmittedRun:
        conversation = await self._conversations.get(conversation_id)
        self._require_access(conversation, user_id)

        started_at = self._now()
        user_message = UserMessage(
            message_id=self._new_message_id(),
            conversation_id=conversation_id,
            content=content,
            created_at=started_at,
        )
        run = Run(
            run_id=self._new_run_id(),
            conversation_id=conversation_id,
            status=RunStatus.CREATED,
            created_at=started_at,
            updated_at=started_at,
        )
        await self._run_starter.start(
            user_message=user_message,
            run=run,
        )

        return SubmittedRun(
            user_message=user_message,
            run=run,
        )

    @staticmethod
    def _require_access(
        conversation: Conversation | None,
        user_id: UserId | None,
    ) -> None:
        if conversation is None:
            raise UnknownConversationError(
                "cannot submit to an unknown conversation",
            )
        if user_id is not None and conversation.user_id != user_id:
            raise ConversationAccessDeniedError("conversation is unavailable")
