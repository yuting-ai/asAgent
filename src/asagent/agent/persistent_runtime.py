from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.loop import AgentLoop
from asagent.agent.run_submission import RunSubmissionService
from asagent.core.ids import ConversationId, MessageId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository
from asagent.core.run import Run
from asagent.core.run_lifecycle import RunFinisher
from asagent.core.run_status import RunStatus
from asagent.models.contracts import ModelMessage, ModelMessageRole


@dataclass(frozen=True, slots=True)
class PersistentAgentRunResult:
    run: Run
    assistant_message: AssistantMessage | None
    error: str | None
    steps_used: int


class PersistentAgentRuntime:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        run_submission: RunSubmissionService,
        run_finisher: RunFinisher,
        loop: AgentLoop,
        now: Callable[[], datetime],
        new_message_id: Callable[[], MessageId],
    ) -> None:
        self._conversations = conversations
        self._run_submission = run_submission
        self._run_finisher = run_finisher
        self._loop = loop
        self._now = now
        self._new_message_id = new_message_id

    async def run(
        self,
        *,
        conversation_id: ConversationId,
        content: str,
        model_name: str,
        system_prompt: str,
        cancellation_token: RunCancellationToken | None = None,
    ) -> PersistentAgentRunResult:
        submission = await self._run_submission.submit(
            conversation_id=conversation_id,
            content=content,
        )
        initial_run = submission.run

        history = await self._conversations.list_messages(conversation_id)
        loop_result = await self._loop.run(
            model_name=model_name,
            system_prompt=system_prompt,
            messages=tuple(self._to_model_message(message) for message in history),
            cancellation_token=cancellation_token,
            run_id=initial_run.run_id,
            conversation_id=conversation_id,
        )

        finished_at = self._now()
        finished_run = Run(
            run_id=initial_run.run_id,
            conversation_id=conversation_id,
            status=loop_result.status,
            created_at=initial_run.created_at,
            updated_at=finished_at,
        )
        assistant_message = self._assistant_message(
            conversation_id=conversation_id,
            text=loop_result.text,
            status=loop_result.status,
            created_at=finished_at,
        )
        await self._run_finisher.finish(
            run=finished_run,
            assistant_message=assistant_message,
        )

        return PersistentAgentRunResult(
            run=finished_run,
            assistant_message=assistant_message,
            error=loop_result.error,
            steps_used=loop_result.steps_used,
        )

    def _assistant_message(
        self,
        *,
        conversation_id: ConversationId,
        text: str | None,
        status: RunStatus,
        created_at: datetime,
    ) -> AssistantMessage | None:
        if status is not RunStatus.COMPLETED or text is None:
            return None

        return AssistantMessage(
            message_id=self._new_message_id(),
            conversation_id=conversation_id,
            content=text,
            created_at=created_at,
        )

    @staticmethod
    def _to_model_message(
        message: UserMessage | AssistantMessage,
    ) -> ModelMessage:
        role = (
            ModelMessageRole.USER
            if isinstance(message, UserMessage)
            else ModelMessageRole.ASSISTANT
        )
        return ModelMessage(role=role, content=message.content)
