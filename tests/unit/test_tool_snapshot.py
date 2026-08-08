import pytest

from asagent.core.tool_definition import ToolDefinition
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.tools.snapshot import ToolSnapshot


def _definition(tool_id: str) -> ToolDefinition:
    return ToolDefinition(
        tool_id=tool_id,
        display_name=tool_id,
        description=f"Description for {tool_id}.",
        input_schema={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        risk_level="low",
        required_permissions=frozenset(),
        requires_approval=False,
        timeout_seconds=1.0,
    )


def test_snapshot_maps_tool_ids_to_provider_names_and_model_tools() -> None:
    calculator = _definition("builtin.calculator")
    current_time = _definition("builtin.current_time")

    snapshot = ToolSnapshot.from_definitions(
        (calculator, current_time),
        provider_name_for=openai_compatible_tool_name,
    )

    assert snapshot.provider_name_for("builtin.calculator") == "builtin_calculator"
    assert snapshot.tool_id_for("builtin_current_time") == "builtin.current_time"
    assert [tool.name for tool in snapshot.model_tools] == [
        "builtin_calculator",
        "builtin_current_time",
    ]
    assert snapshot.model_tools[0].input_schema == calculator.input_schema


def test_snapshot_rejects_provider_name_collisions() -> None:
    with pytest.raises(ValueError, match="duplicate provider_name"):
        ToolSnapshot.from_definitions(
            (_definition("one.two"), _definition("one_two")),
            provider_name_for=openai_compatible_tool_name,
        )


def test_snapshot_rejects_unknown_names() -> None:
    snapshot = ToolSnapshot.from_definitions(
        (_definition("builtin.echo"),),
        provider_name_for=openai_compatible_tool_name,
    )

    with pytest.raises(KeyError, match="tool_id is not in snapshot"):
        snapshot.provider_name_for("builtin.unknown")

    with pytest.raises(KeyError, match="provider_name is not in snapshot"):
        snapshot.tool_id_for("builtin_unknown")


def test_openai_compatible_name_normalizes_and_enforces_length() -> None:
    assert openai_compatible_tool_name("mcp:server/read") == "mcp_server_read"

    with pytest.raises(ValueError, match="cannot be converted"):
        openai_compatible_tool_name("a" * 65)
