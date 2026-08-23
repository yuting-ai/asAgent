import asyncio
from datetime import UTC, datetime, time

import pytest

from asagent.agent.run_dispatcher import RunDispatchOutcome
from asagent.agent.run_submission import SubmittedRun
from asagent.automation.scheduler import (
    AutomationRunSubmissionService,
    AutomationScheduler,
)
from asagent.core.automation import (
    Automation,
    AutomationExecution,
    AutomationExecutionStatus,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
)
from asagent.core.conversation import Conversation
from asagent.core.ids import (
    AutomationExecutionId,
    AutomationId,
    AutomationTriggerId,
    ConversationId,
    MessageId,
    RunId,
    UserId,
)
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus


def _now() -> datetime:
    return datetime(2026, 8, 20, 1, 5, tzinfo=UTC)


def _automation() -> Automation:
    now = _now()
    return Automation(
        AutomationId("automation-1"),
        UserId("local-user"),
        "Morning report",
        "Summarize the report.",
        ("mcp.reports.read",),
        AutomationStatus.ACTIVE,
        now,
        now,
    )


def _execution() -> AutomationExecution:
    now = _now()
    return AutomationExecution(
        AutomationExecutionId("execution-1"),
        AutomationId("automation-1"),
        AutomationTriggerId("trigger-1"),
        now,
        AutomationExecutionStatus.CLAIMED,
        now,
    )


class _Automations:
    def __init__(self, executions: tuple[AutomationExecution, ...]) -> None:
        self.executions = executions
        self.saved: list[AutomationExecution] = []

    async def claim_due(
        self,
        now: datetime,
        *,
        missed_before: datetime | None = None,
        limit: int = 100,
    ) -> tuple[AutomationExecution, ...]:
        del now, missed_before, limit
        executions = self.executions
        self.executions = ()
        return executions

    async def get(self, automation_id: AutomationId) -> Automation | None:
        return _automation() if automation_id == AutomationId("automation-1") else None

    async def list_triggers(
        self, automation_id: AutomationId
    ) -> tuple[AutomationTrigger, ...]:
        if automation_id != AutomationId("automation-1"):
            return ()
        now = _now()
        return (
            AutomationTrigger(
                AutomationTriggerId("trigger-1"),
                automation_id,
                AutomationTriggerKind.DAILY,
                "Australia/Perth",
                time(9),
                None,
                now,
                True,
                now,
                now,
            ),
        )

    async def save_execution(self, execution: AutomationExecution) -> None:
        self.saved.append(execution)


class _Submission:
    async def submit(
        self, *, automation: Automation, execution: AutomationExecution
    ) -> SubmittedRun:
        now = _now()
        conversation_id = ConversationId("automation-conversation-1")
        del automation, execution
        return SubmittedRun(
            UserMessage(MessageId("message-1"), conversation_id, "run", now),
            Run(RunId("run-1"), conversation_id, RunStatus.CREATED, now, now),
            Conversation(conversation_id, UserId("local-user"), now, now),
        )


class _Handle:
    async def wait(self) -> RunDispatchOutcome:
        return RunDispatchOutcome(RunId("run-1"), None, False)


class _Dispatcher:
    def dispatch(self, submission: SubmittedRun) -> _Handle:
        assert submission.run.run_id == RunId("run-1")
        return _Handle()


class _Runs:
    async def get(self, run_id: RunId) -> Run | None:
        now = _now()
        return Run(
            run_id,
            ConversationId("automation-conversation-1"),
            RunStatus.COMPLETED,
            now,
            now,
        )


class _ConversationStore:
    def __init__(self) -> None:
        self.saved: list[Conversation] = []

    async def save(self, conversation: Conversation) -> None:
        self.saved.append(conversation)

    async def delete(self, conversation_id: ConversationId) -> bool:
        del conversation_id
        return True


class _RunSubmission:
    async def submit(
        self,
        *,
        conversation_id: ConversationId,
        user_id: UserId,
        content: str,
    ) -> SubmittedRun:
        now = _now()
        return SubmittedRun(
            UserMessage(MessageId("message-2"), conversation_id, content, now),
            Run(RunId("run-2"), conversation_id, RunStatus.CREATED, now, now),
            Conversation(
                conversation_id, user_id, now, now, kind="automation_execution"
            ),
        )


@pytest.mark.asyncio
async def test_automation_execution_uses_a_hidden_conversation_kind() -> None:
    conversations = _ConversationStore()
    from asagent.automation.scheduler import AutomationExecutionContextStore

    execution_contexts = AutomationExecutionContextStore()
    submission = AutomationRunSubmissionService(
        conversations=conversations,  # type: ignore[arg-type]
        run_submission=_RunSubmission(),  # type: ignore[arg-type]
        now=_now,
        new_conversation_id=lambda: ConversationId("automation-execution-conversation"),
        execution_contexts=execution_contexts,
    )

    submitted = await submission.submit(
        automation=_automation(), execution=_execution()
    )

    assert submitted.run.conversation_id == ConversationId(
        "automation-execution-conversation"
    )
    assert conversations.saved[0].kind == "automation_execution"
    assert execution_contexts.target(
        ConversationId("automation-execution-conversation")
    ) == AutomationId("automation-1")


@pytest.mark.asyncio
async def test_tick_submits_claimed_execution_and_records_the_terminal_run_status() -> (
    None
):
    automations = _Automations((_execution(),))
    scheduler = AutomationScheduler(
        automations=automations,  # type: ignore[arg-type]
        runs=_Runs(),  # type: ignore[arg-type]
        submission=_Submission(),  # type: ignore[arg-type]
        dispatcher=_Dispatcher(),  # type: ignore[arg-type]
        now=_now,
    )

    await scheduler.tick()
    await asyncio.sleep(0)

    assert [execution.status for execution in automations.saved] == [
        AutomationExecutionStatus.CLAIMED,
        AutomationExecutionStatus.COMPLETED,
    ]
    assert automations.saved[-1].run_id == RunId("run-1")


@pytest.mark.asyncio
async def test_start_marks_overdue_occurrences_as_missed_without_dispatching() -> None:
    missed = AutomationExecution(
        AutomationExecutionId("execution-1"),
        AutomationId("automation-1"),
        AutomationTriggerId("trigger-1"),
        _now(),
        AutomationExecutionStatus.MISSED,
        _now(),
    )
    automations = _Automations((missed,))
    scheduler = AutomationScheduler(
        automations=automations,  # type: ignore[arg-type]
        runs=_Runs(),  # type: ignore[arg-type]
        submission=_Submission(),  # type: ignore[arg-type]
        dispatcher=_Dispatcher(),  # type: ignore[arg-type]
        now=_now,
        poll_interval_seconds=60,
    )

    await scheduler.start()
    await scheduler.aclose()

    assert automations.saved == []


@pytest.mark.asyncio
async def test_run_now_records_a_real_execution_without_mutating_the_trigger() -> None:
    automations = _Automations(())
    scheduler = AutomationScheduler(
        automations=automations,  # type: ignore[arg-type]
        runs=_Runs(),  # type: ignore[arg-type]
        submission=_Submission(),  # type: ignore[arg-type]
        dispatcher=_Dispatcher(),  # type: ignore[arg-type]
        now=_now,
    )

    execution = await scheduler.run_now(AutomationId("automation-1"))
    await asyncio.sleep(0)

    assert execution.status is AutomationExecutionStatus.CLAIMED
    assert execution.automation_trigger_id == AutomationTriggerId("trigger-1")
    assert [value.status for value in automations.saved] == [
        AutomationExecutionStatus.CLAIMED,
        AutomationExecutionStatus.CLAIMED,
        AutomationExecutionStatus.COMPLETED,
    ]
