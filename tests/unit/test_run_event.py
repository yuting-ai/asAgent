from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from ragent.core.ids import ConversationId, EventId, RunId
from ragent.core.run_event import RunEvent


def test_run_event_preserves_identity_order_and_payload() -> None:
    payload = {"text": "Hello, Ragent."}
    created_at = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)

    event = RunEvent(
        event_id=EventId("evt_123"),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        sequence=2,
        event_type="model.delta",
        created_at=created_at,
        data=payload,
    )

    assert event.event_id == "evt_123"
    assert event.run_id == "run_123"
    assert event.conversation_id == "conv_123"
    assert event.sequence == 2
    assert event.event_type == "model.delta"
    assert event.created_at == created_at
    assert event.data == {"text": "Hello, Ragent."}

    payload["text"] = "Changed after publishing."
    assert event.data == {"text": "Hello, Ragent."}


def test_run_event_sequence_must_start_at_one() -> None:
    with pytest.raises(ValueError, match="sequence must be at least 1"):
        RunEvent(
            event_id=EventId("evt_123"),
            run_id=RunId("run_123"),
            conversation_id=ConversationId("conv_123"),
            sequence=0,
            event_type="run.started",
            created_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
            data={},
        )


def test_run_event_is_immutable() -> None:
    event = RunEvent(
        event_id=EventId("evt_123"),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        sequence=1,
        event_type="run.started",
        created_at=datetime(2026, 8, 3, 10, 0, tzinfo=UTC),
        data={},
    )

    with pytest.raises(FrozenInstanceError):
        event.sequence = 2  # type: ignore[misc]
