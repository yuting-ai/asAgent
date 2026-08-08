import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.calculator import CalculatorTool


def test_calculator_tool_satisfies_protocol_and_describes_input() -> None:
    tool: Tool = CalculatorTool()

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "builtin.calculator"
    assert tool.definition.input_schema["required"] == ["expression"]


@pytest.mark.asyncio
async def test_calculator_tool_respects_precedence_and_parentheses() -> None:
    tool = CalculatorTool()

    result = await tool.execute({"expression": "-(2 + 3) * 4 / 2"})

    assert result == "-10.0"


@pytest.mark.asyncio
async def test_calculator_tool_rejects_python_code() -> None:
    tool = CalculatorTool()

    with pytest.raises(ValueError, match="unsupported syntax"):
        await tool.execute({"expression": "__import__('os').system('whoami')"})
