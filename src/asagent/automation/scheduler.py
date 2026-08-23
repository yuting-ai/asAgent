import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from asagent.agent.run_dispatcher import InProcessRunDispatcher
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.core.automation import (
    Automation,
    AutomationExecution,
    AutomationExecutionStatus,
)
from asagent.core.conversation import Conversation
from asagent.core.ids import AutomationExecutionId, AutomationId, ConversationId, RunId
from asagent.core.repositories import (
    AutomationRepository,
    ConversationRepository,
    RunRepository,
)
from asagent.core.run_status import RunStatus


class AutomationExecutionContextStore:
    """Process-local mapping between an active automation execution conversation and its automation ID."""

    def __init__(self) -> None:
        self._contexts: dict[ConversationId, AutomationId] = {}

    def bind(
        self, conversation_id: ConversationId, automation_id: AutomationId
    ) -> None:
        self._contexts[conversation_id] = automation_id

    def target(self, conversation_id: ConversationId) -> AutomationId | None:
        return self._contexts.get(conversation_id)

    def remove(self, conversation_id: ConversationId) -> None:
        self._contexts.pop(conversation_id, None)


class AutomationRunSubmissionService:
    """Creates one isolated conversation and submitted Run for an execution."""

    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        run_submission: RunSubmissionService,
        now: Callable[[], datetime],
        new_conversation_id: Callable[[], ConversationId],
        execution_contexts: AutomationExecutionContextStore | None = None,
    ) -> None:
        self._conversations = conversations
        self._run_submission = run_submission
        self._now = now
        self._new_conversation_id = new_conversation_id
        self._execution_contexts = execution_contexts

    async def submit(
        self,
        *,
        automation: Automation,
        execution: AutomationExecution,
    ) -> SubmittedRun:
        now = self._now()
        conversation = Conversation(
            conversation_id=self._new_conversation_id(),
            user_id=automation.user_id,
            created_at=now,
            updated_at=now,
            title=automation.name,
            kind="automation_execution",
        )
        await self._conversations.save(conversation)
        if self._execution_contexts is not None:
            self._execution_contexts.bind(
                conversation.conversation_id, automation.automation_id
            )
        try:
            return await self._run_submission.submit(
                conversation_id=conversation.conversation_id,
                user_id=automation.user_id,
                content=_automation_prompt(automation, execution),
            )
        except Exception:
            if self._execution_contexts is not None:
                self._execution_contexts.remove(conversation.conversation_id)
            await self._conversations.delete(conversation.conversation_id)
            raise


class AutomationScheduler:
    """Owns the in-process scheduling loop, but not Runtime or database setup."""

    def __init__(
        self,
        *,
        automations: AutomationRepository,
        runs: RunRepository,
        submission: AutomationRunSubmissionService,
        dispatcher: InProcessRunDispatcher,
        now: Callable[[], datetime],
        poll_interval_seconds: float = 30.0,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self._automations = automations
        self._runs = runs
        self._submission = submission
        self._dispatcher = dispatcher
        self._now = now
        self._poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("automation scheduler is closed")
        if self._task is not None:
            return
        await self.tick(recover_missed=True)
        self._task = asyncio.create_task(
            self._run(), name="asagent-automation-scheduler"
        )

    async def aclose(self) -> None:
        self._closed = True
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def tick(self, *, recover_missed: bool = False) -> None:
        now = self._now()
        executions = await self._automations.claim_due(
            now,
            missed_before=now if recover_missed else None,
        )
        for execution in executions:
            if execution.status is AutomationExecutionStatus.CLAIMED:
                await self._submit_and_dispatch(execution)

    async def run_now(self, automation_id: AutomationId) -> AutomationExecution:
        """Submit one manual execution without changing the trigger schedule."""
        automation = await self._automations.get(automation_id)
        if automation is None:
            raise ValueError("automation not found")
        triggers = await self._automations.list_triggers(automation_id)
        if len(triggers) != 1:
            raise ValueError("automation must have exactly one trigger")
        now = self._now()
        execution = AutomationExecution(
            AutomationExecutionId(f"automation_execution_{uuid4().hex}"),
            automation_id,
            triggers[0].automation_trigger_id,
            now,
            AutomationExecutionStatus.CLAIMED,
            now,
        )
        await self._automations.save_execution(execution)
        await self._submit_and_dispatch(execution)
        return execution

    async def _run(self) -> None:
        while not self._closed:
            await asyncio.sleep(self._poll_interval_seconds)
            try:
                await self.tick()
            except Exception:
                # One failed tick must not permanently stop later automations.
                continue

    async def _submit_and_dispatch(self, execution: AutomationExecution) -> None:
        automation = await self._automations.get(execution.automation_id)
        if automation is None:
            await self._finish(execution, AutomationExecutionStatus.FAILED, None)
            return
        try:
            submitted = await self._submission.submit(
                automation=automation,
                execution=execution,
            )
            linked = replace(execution, run_id=submitted.run.run_id)
            await self._automations.save_execution(linked)
            handle = self._dispatcher.dispatch(submitted)
        except Exception:
            await self._finish(execution, AutomationExecutionStatus.FAILED, None)
            return
        asyncio.create_task(
            self._record_completion(linked, handle.wait),
            name=f"asagent-automation-execution-{execution.automation_execution_id}",
        )

    async def _record_completion(
        self,
        execution: AutomationExecution,
        wait: Callable[[], Awaitable[object]],
    ) -> None:
        # Dispatcher captures executor errors; the persisted Run remains source of truth.
        await wait()
        assert execution.run_id is not None
        run = await self._runs.get(execution.run_id)
        if run is None or run.status in {RunStatus.FAILED, RunStatus.LIMIT_REACHED}:
            status = AutomationExecutionStatus.FAILED
        elif run.status is RunStatus.CANCELLED:
            status = AutomationExecutionStatus.CANCELLED
        else:
            status = AutomationExecutionStatus.COMPLETED
        await self._finish(execution, status, execution.run_id)

    async def _finish(
        self,
        execution: AutomationExecution,
        status: AutomationExecutionStatus,
        run_id: RunId | None,
    ) -> None:
        await self._automations.save_execution(
            replace(
                execution,
                status=status,
                run_id=run_id,
                completed_at=self._now(),
            )
        )


def _automation_prompt(automation: Automation, execution: AutomationExecution) -> str:
    capabilities = ", ".join(automation.allowed_capabilities) or "none"
    return (
        f"This is an isolated execution of scheduled task: {automation.name}\n"
        f"Scheduled for: {execution.scheduled_for.isoformat()}\n"
        f"Allowed capabilities: {capabilities}\n\n"
        f"Task plan & instructions:\n{automation.plan_summary}\n\n"
        "Execution guidelines:\n"
        "1. Follow the task plan and instructions above to accomplish the objective.\n"
        "2. Self-healing / Error Recovery: If any step fails (e.g. a link returns 400/404, a webpage changed layout, or a selector is invalid), actively troubleshoot and use alternative valid URLs or methods to complete the task.\n"
        "3. Plan Optimization: If you had to modify or adapt the steps/URLs to succeed, call `automation.update_plan` with the updated, complete instructions (`refined_plan_summary`) so all future scheduled executions directly use the working method.\n"
        "4. If you use the automation browser during this execution, remember to call `automation_browser.close` when finished to close the browser window."
    )
