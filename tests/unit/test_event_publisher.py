from datetime import UTC, datetime

import pytest

from ragent.core.event_publisher import EventPublisher
from ragent.core.ids import ConversationId, EventId, RunId
from ragent.core.run_event import RunEvent


class CollectingEventPublisher:
    def __init__(self) -> None:
        self.published: list[RunEvent] = []

    async def publish(self, event: RunEvent) -> None:
        self.published.append(event)


@pytest.mark.asyncio
async def test_collecting_event_publisher_satisfies_protocol() -> None:
    collector = CollectingEventPublisher()
    publisher: EventPublisher = collector
    event = RunEvent(
        event_id=EventId("evt_123"),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        sequence=1,
        event_type="run.started",
        created_at=datetime(2026, 8, 4, 11, 0, tzinfo=UTC),
        data={},
    )

    assert isinstance(publisher, EventPublisher)

    await publisher.publish(event)

    assert collector.published == [event]
