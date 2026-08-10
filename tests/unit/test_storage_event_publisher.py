from datetime import UTC, datetime

import pytest

from asagent.core.event_publisher import EventPublisher
from asagent.core.ids import ConversationId, EventId, RunId
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.tool_call import ToolCall
from asagent.storage.event_publisher import RepositoryEventPublisher


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
        raise self._error

    async def list_events(
        self,
        run_id: RunId,
        *,
        after_sequence: int = 0,
    ) -> tuple[RunEvent, ...]:
        return ()

    async def save_tool_call(self, tool_call: ToolCall) -> None:
        pass

    async def list_tool_calls(self, run_id: RunId) -> tuple[ToolCall, ...]:
        return ()


def _event() -> RunEvent:
    return RunEvent(
        event_id=EventId("event-1"),
        run_id=RunId("run-1"),
        conversation_id=ConversationId("conversation-1"),
        sequence=1,
        event_type="run.started",
        created_at=datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
        data={},
    )


@pytest.mark.asyncio
async def test_publisher_satisfies_protocol_and_propagates_repository_error() -> None:
    expected_error = RuntimeError("database write failed")
    repository: RunRepository = FailingRunRepository(expected_error)
    publisher = RepositoryEventPublisher(repository)
    protocol: EventPublisher = publisher

    assert isinstance(protocol, EventPublisher)

    with pytest.raises(RuntimeError) as captured:
        await publisher.publish(_event())

    assert captured.value is expected_error
