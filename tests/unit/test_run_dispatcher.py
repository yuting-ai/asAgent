import asyncio
from datetime import UTC, datetime

import pytest

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.run_dispatcher import InProcessRunDispatcher
from asagent.agent.run_submission import SubmittedRun
from asagent.core.ids import ConversationId, MessageId, RunId
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus

_DEFAULT_RUN_ID = RunId("run-1")


def _submission(run_id: RunId = _DEFAULT_RUN_ID) -> SubmittedRun:
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversation_id = ConversationId("conversation-1")
    return SubmittedRun(
        user_message=UserMessage(
            message_id=MessageId("message-1"),
            conversation_id=conversation_id,
            content="Hello",
            created_at=created_at,
        ),
        run=Run(
            run_id=run_id,
            conversation_id=conversation_id,
            status=RunStatus.CREATED,
            created_at=created_at,
            updated_at=created_at,
        ),
    )


@pytest.mark.asyncio
async def test_dispatch_runs_in_the_background_and_cleans_up_after_completion() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        del submission
        del cancellation_token
        started.set()
        await release.wait()

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    submission = _submission()

    handle = dispatcher.dispatch(submission)

    assert handle.run_id == RunId("run-1")
    assert dispatcher.is_active(RunId("run-1")) is True

    await started.wait()
    release.set()

    outcome = await handle.wait()

    assert outcome.run_id == RunId("run-1")
    assert outcome.error is None
    assert outcome.cancel_requested is False
    assert dispatcher.is_active(RunId("run-1")) is False


@pytest.mark.asyncio
async def test_dispatch_rejects_an_already_active_run() -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        del submission
        del cancellation_token
        started.set()
        await release.wait()

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    submission = _submission()

    handle = dispatcher.dispatch(submission)
    await started.wait()

    with pytest.raises(ValueError, match="run is already active"):
        dispatcher.dispatch(submission)

    release.set()
    await handle.wait()


@pytest.mark.asyncio
async def test_cancel_marks_the_token_passed_to_the_executor() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    received_token = None

    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        nonlocal received_token
        del submission
        received_token = cancellation_token
        started.set()
        await release.wait()

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    handle = dispatcher.dispatch(_submission())

    await started.wait()

    assert dispatcher.cancel(RunId("run-1")) is True
    assert dispatcher.cancel(RunId("missing")) is False

    release.set()
    outcome = await handle.wait()

    assert received_token is not None
    assert received_token.is_cancelled is True
    assert outcome.cancel_requested is True
    assert dispatcher.is_active(RunId("run-1")) is False


@pytest.mark.asyncio
async def test_dispatch_captures_executor_error_and_cleans_up() -> None:
    expected_error = RuntimeError("execution failed")

    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        del submission
        del cancellation_token
        raise expected_error

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    handle = dispatcher.dispatch(_submission())

    outcome = await handle.wait()

    assert outcome.error is expected_error
    assert outcome.cancel_requested is False
    assert dispatcher.is_active(RunId("run-1")) is False


@pytest.mark.asyncio
async def test_aclose_cancels_active_runs_and_cleans_up() -> None:
    started = asyncio.Event()

    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        del submission
        started.set()
        while not cancellation_token.is_cancelled:
            await asyncio.sleep(0)

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    handle = dispatcher.dispatch(_submission())

    await started.wait()
    assert dispatcher.is_active(RunId("run-1")) is True

    await dispatcher.aclose()
    outcome = await handle.wait()

    assert outcome.cancel_requested is True
    assert outcome.error is None
    assert dispatcher.is_active(RunId("run-1")) is False


@pytest.mark.asyncio
async def test_aclose_rejects_later_dispatch() -> None:
    async def execute(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        del submission
        del cancellation_token

    dispatcher = InProcessRunDispatcher(execute_submitted=execute)
    await dispatcher.aclose()

    with pytest.raises(RuntimeError, match="run dispatcher is closed"):
        dispatcher.dispatch(_submission())
