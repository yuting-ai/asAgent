import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.run_submission import SubmittedRun
from asagent.core.ids import RunId

SubmittedRunExecutor = Callable[
    [SubmittedRun, RunCancellationToken],
    Awaitable[None],
]


@dataclass(frozen=True, slots=True)
class RunDispatchOutcome:
    run_id: RunId
    error: Exception | None
    cancel_requested: bool


class RunDispatchHandle:
    def __init__(
        self,
        *,
        run_id: RunId,
        task: asyncio.Task[RunDispatchOutcome],
    ) -> None:
        self._run_id = run_id
        self._task = task

    @property
    def run_id(self) -> RunId:
        return self._run_id

    async def wait(self) -> RunDispatchOutcome:
        return await self._task


class InProcessRunDispatcher:
    def __init__(
        self,
        *,
        execute_submitted: SubmittedRunExecutor,
    ) -> None:
        self._execute_submitted = execute_submitted
        self._tokens: dict[RunId, RunCancellationToken] = {}

    def dispatch(self, submission: SubmittedRun) -> RunDispatchHandle:
        run_id = submission.run.run_id
        if run_id in self._tokens:
            raise ValueError("run is already active")

        token = RunCancellationToken(run_id)
        self._tokens[run_id] = token
        task = asyncio.create_task(
            self._execute(
                submission=submission,
                cancellation_token=token,
            ),
            name=f"asagent-run-{run_id}",
        )
        return RunDispatchHandle(run_id=run_id, task=task)

    def cancel(self, run_id: RunId) -> bool:
        token = self._tokens.get(run_id)
        if token is None:
            return False

        token.cancel()
        return True

    def is_active(self, run_id: RunId) -> bool:
        return run_id in self._tokens

    async def _execute(
        self,
        *,
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> RunDispatchOutcome:
        run_id = submission.run.run_id

        try:
            await self._execute_submitted(submission, cancellation_token)
        except Exception as error:
            return RunDispatchOutcome(
                run_id=run_id,
                error=error,
                cancel_requested=cancellation_token.is_cancelled,
            )
        finally:
            self._tokens.pop(run_id, None)

        return RunDispatchOutcome(
            run_id=run_id,
            error=None,
            cancel_requested=cancellation_token.is_cancelled,
        )
