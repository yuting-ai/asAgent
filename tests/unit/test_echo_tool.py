import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.echo import EchoTool


def test_echo_tool_satisfies_protocol_and_describes_input() -> None:
    tool: Tool = EchoTool()

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "builtin.echo"
    assert tool.definition.risk_level == "low"
    assert tool.definition.requires_approval is False
    assert tool.definition.input_schema["required"] == ["text"]


@pytest.mark.asyncio
async def test_echo_tool_returns_supplied_text() -> None:
    tool = EchoTool()

    result = await tool.execute({"text": "hello"})
    assert result == "Echo: hello"
