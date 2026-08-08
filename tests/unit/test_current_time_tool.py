from datetime import UTC, datetime

import pytest

from asagent.core.tool import Tool
from asagent.tools.builtin.current_time import CurrentTimeTool


def test_current_time_tool_satisfies_protocol_and_describes_input() -> None:
    tool: Tool = CurrentTimeTool()

    assert isinstance(tool, Tool)
    assert tool.definition.tool_id == "builtin.current_time"
    assert tool.definition.input_schema["properties"] == {}


@pytest.mark.asyncio
async def test_current_time_tool_returns_injected_time_in_utc() -> None:
    fixed_time = datetime(2026, 8, 8, 12, 34, 56, tzinfo=UTC)
    tool = CurrentTimeTool(now=lambda: fixed_time)

    result = await tool.execute({})

    assert result == "2026-08-08T12:34:56+00:00"


@pytest.mark.asyncio
async def test_current_time_tool_rejects_naive_time() -> None:
    tool = CurrentTimeTool(now=lambda: datetime(2026, 8, 8, 12, 34, 56))

    with pytest.raises(ValueError, match="timezone-aware"):
        await tool.execute({})
