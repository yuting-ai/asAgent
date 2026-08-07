from dataclasses import FrozenInstanceError

import pytest

from asagent.core.tool_definition import ToolDefinition


def make_tool_definition(
    *,
    timeout_seconds: float = 10.0,
) -> ToolDefinition:
    return ToolDefinition(
        tool_id="builtin.echo",
        display_name="Echo",
        description="Returns the supplied text.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
        },
        risk_level="low",
        required_permissions=frozenset({"tool.execute"}),
        requires_approval=False,
        timeout_seconds=timeout_seconds,
    )


def test_tool_definition_preserves_metadata_and_snapshots_schema() -> None:
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }

    definition = ToolDefinition(
        tool_id="builtin.echo",
        display_name="Echo",
        description="Returns the supplied text.",
        input_schema=input_schema,
        risk_level="low",
        required_permissions=frozenset({"tool.execute"}),
        requires_approval=False,
        timeout_seconds=10.0,
    )

    assert definition.tool_id == "builtin.echo"
    assert definition.display_name == "Echo"
    assert definition.description == "Returns the supplied text."
    assert definition.input_schema["type"] == "object"
    assert definition.risk_level == "low"
    assert definition.required_permissions == frozenset({"tool.execute"})
    assert not definition.requires_approval
    assert definition.timeout_seconds == 10.0

    input_schema["type"] = "array"
    assert definition.input_schema["type"] == "object"


def test_tool_definition_requires_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        make_tool_definition(timeout_seconds=0)


def test_tool_definition_is_immutable() -> None:
    definition = make_tool_definition()

    with pytest.raises(FrozenInstanceError):
        setattr(  # noqa: B010
            definition,
            "display_name",
            "Changed",
        )
