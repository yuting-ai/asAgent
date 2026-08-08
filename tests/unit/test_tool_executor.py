from collections.abc import Mapping

import pytest

from asagent.core.tool_definition import ToolDefinition
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry


class RecordingTool:
    def __init__(self) -> None:
        self.arguments: Mapping[str, object] | None = None

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.echo",
            display_name="Echo",
            description="Returns supplied text.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        self.arguments = arguments
        return f"Echo: {arguments['text']}"


class FailingTool(RecordingTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.fail",
            display_name="Fail",
            description="Always fails.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        raise RuntimeError("tool failed")


@pytest.mark.asyncio
async def test_executor_delegates_to_registered_tool() -> None:
    tool = RecordingTool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    result = await executor.execute("builtin.echo", {"text": "hello"})

    assert result == "Echo: hello"
    assert tool.arguments == {"text": "hello"}


@pytest.mark.asyncio
async def test_executor_rejects_unknown_tool_id() -> None:
    executor = ToolExecutor(ToolRegistry())

    with pytest.raises(KeyError, match="not registered"):
        await executor.execute("builtin.echo", {})


@pytest.mark.asyncio
async def test_executor_does_not_hide_tool_failure() -> None:
    registry = ToolRegistry()
    registry.register(FailingTool())
    executor = ToolExecutor(registry)

    with pytest.raises(RuntimeError, match="tool failed"):
        await executor.execute("builtin.fail", {})
