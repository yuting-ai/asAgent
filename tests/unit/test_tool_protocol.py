from collections.abc import Mapping

import pytest

from asagent.core.tool import Tool
from asagent.core.tool_definition import ToolDefinition


class ExampleTool:
    @property
    def definition(self) -> ToolDefinition:
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
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        return f"Echo: {arguments['text']}"


@pytest.mark.asyncio
async def test_example_tool_satisfies_protocol_and_executes() -> None:
    tool: Tool = ExampleTool()

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "builtin.echo"
    assert await tool.execute({"text": "Hello, asAgent."}) == "Echo: Hello, asAgent."
