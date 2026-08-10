from datetime import UTC, datetime

import pytest

from asagent.core.ids import ConversationId, RunId, ToolCallId
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.tool_call import ToolCall
from asagent.core.tool_call_recorder import ToolCallRecorder
from asagent.storage.tool_call_recorder import RepositoryToolCallRecorder


class FailingRunRepository:
    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get(self, run_id: RunId) -> Run | None:
        return None

    async def list_for_conversation(
        self,
        conversation_id: ConversationId,
    ) -> tuple[Run, ...]:
        return ()

    async def save(self, run: Run) -> None:
        pass

    async def append_event(self, event: RunEvent) -> None:
        pass

    async def list_events(
        self,
        run_id: RunId,
        *,
        after_sequence: int = 0,
    ) -> tuple[RunEvent, ...]:
        return ()

    async def save_tool_call(self, tool_call: ToolCall) -> None:
        raise self._error

    async def list_tool_calls(
        self,
        run_id: RunId,
    ) -> tuple[ToolCall, ...]:
        return ()


def _tool_call() -> ToolCall:
    return ToolCall(
        tool_call_id=ToolCallId("tool-call-1"),
        run_id=RunId("run-1"),
        model_call_id="model-call-1",
        tool_id="builtin.calculator",
        arguments={"expression": "123 * 456"},
        result="56088",
        error=None,
        created_at=datetime(2026, 8, 10, 15, 0, tzinfo=UTC),
        completed_at=datetime(2026, 8, 10, 15, 0, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_recorder_satisfies_protocol_and_propagates_repository_error() -> None:
    expected_error = RuntimeError("database write failed")
    repository: RunRepository = FailingRunRepository(expected_error)
    recorder = RepositoryToolCallRecorder(repository)
    protocol: ToolCallRecorder = recorder

    assert isinstance(protocol, ToolCallRecorder)

    with pytest.raises(RuntimeError) as captured:
        await recorder.record(_tool_call())

    assert captured.value is expected_error
