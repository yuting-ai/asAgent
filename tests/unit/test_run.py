from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from ragent.core.ids import ConversationId, RunId
from ragent.core.run import Run
from ragent.core.run_status import RunStatus


def test_run_preserves_execution_identity_and_state() -> None:
    created_at = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 3, 9, 1, tzinfo=UTC)

    run = Run(
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        status=RunStatus.CALLING_MODEL,
        created_at=created_at,
        updated_at=updated_at,
    )

    assert run.run_id == "run_123"
    assert run.conversation_id == "conv_123"
    assert run.status is RunStatus.CALLING_MODEL
    assert run.created_at == created_at
    assert run.updated_at == updated_at


def test_run_is_immutable() -> None:
    created_at = datetime(2026, 8, 3, 9, 0, tzinfo=UTC)
    run = Run(
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
        status=RunStatus.CREATED,
        created_at=created_at,
        updated_at=created_at,
    )

    with pytest.raises(FrozenInstanceError):
        run.status = RunStatus.CANCELLED  # type: ignore[misc]
