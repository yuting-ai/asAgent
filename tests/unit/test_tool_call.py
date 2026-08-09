from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from asagent.core.ids import RunId, ToolCallId
from asagent.core.tool_call import ToolCall


def test_tool_call_preserves_request_and_result() -> None:
    arguments = {"expression": "2 + 2"}
    created_at = datetime(2026, 8, 3, 11, 0, tzinfo=UTC)
    completed_at = datetime(2026, 8, 3, 11, 0, 1, tzinfo=UTC)

    tool_call = ToolCall(
        tool_call_id=ToolCallId("tool_123"),
        run_id=RunId("run_123"),
        model_call_id="call_123",
        tool_id="builtin.calculator",
        arguments=arguments,
        result="4",
        error=None,
        created_at=created_at,
        completed_at=completed_at,
    )

    assert tool_call.tool_call_id == "tool_123"
    assert tool_call.run_id == "run_123"
    assert tool_call.model_call_id == "call_123"
    assert tool_call.tool_id == "builtin.calculator"
    assert tool_call.arguments == {"expression": "2 + 2"}
    assert tool_call.result == "4"
    assert tool_call.error is None
    assert tool_call.created_at == created_at
    assert tool_call.completed_at == completed_at

    arguments["expression"] = "changed"
    assert tool_call.arguments == {"expression": "2 + 2"}


def test_tool_call_can_be_pending() -> None:
    tool_call = ToolCall(
        tool_call_id=ToolCallId("tool_123"),
        run_id=RunId("run_123"),
        model_call_id="call_123",
        tool_id="builtin.calculator",
        arguments={"expression": "2 + 2"},
        result=None,
        error=None,
        created_at=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        completed_at=None,
    )

    assert tool_call.result is None
    assert tool_call.error is None
    assert tool_call.completed_at is None


def test_tool_call_rejects_result_and_error_together() -> None:
    with pytest.raises(ValueError, match="result and error cannot both be set"):
        ToolCall(
            tool_call_id=ToolCallId("tool_123"),
            run_id=RunId("run_123"),
            model_call_id="call_123",
            tool_id="builtin.calculator",
            arguments={},
            result="4",
            error="unexpected failure",
            created_at=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
            completed_at=datetime(2026, 8, 3, 11, 0, 1, tzinfo=UTC),
        )


def test_tool_call_is_immutable() -> None:
    tool_call = ToolCall(
        tool_call_id=ToolCallId("tool_123"),
        run_id=RunId("run_123"),
        model_call_id="call_123",
        tool_id="builtin.calculator",
        arguments={},
        result=None,
        error=None,
        created_at=datetime(2026, 8, 3, 11, 0, tzinfo=UTC),
        completed_at=None,
    )

    with pytest.raises(FrozenInstanceError):
        tool_call.result = "4"  # type: ignore[misc]
