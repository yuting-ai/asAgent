import pytest

from asagent.core.tool import Tool
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.registry import ToolRegistry


class StubTool:
    def __init__(self, tool_id: str) -> None:
        self._definition = ToolDefinition(
            tool_id=tool_id,
            display_name=tool_id,
            description="Test tool.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(self, arguments: object) -> str:
        return "unused"


def test_register_and_get_tool() -> None:
    tool: Tool = StubTool("builtin.echo")
    registry = ToolRegistry()

    registry.register(tool)

    assert registry.get("builtin.echo") is tool
    assert registry.definitions() == (tool.definition,)


def test_duplicate_tool_id_is_rejected_without_overwriting() -> None:
    original: Tool = StubTool("builtin.echo")
    duplicate: Tool = StubTool("builtin.echo")
    registry = ToolRegistry()
    registry.register(original)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(duplicate)

    assert registry.get("builtin.echo") is original


def test_unknown_tool_id_is_rejected() -> None:
    registry = ToolRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.get("builtin.echo")


def test_copy_keeps_tools_without_sharing_registry_mutations() -> None:
    original: Tool = StubTool("builtin.echo")
    copied_only: Tool = StubTool("builtin.calculator")
    registry = ToolRegistry()
    registry.register(original)

    copied = registry.copy()
    copied.register(copied_only)

    assert copied.get("builtin.echo") is original
    assert copied.get("builtin.calculator") is copied_only
    assert registry.definitions() == (original.definition,)


def test_replace_with_updates_tools_atomically() -> None:
    original: Tool = StubTool("builtin.echo")
    replacement: Tool = StubTool("builtin.calculator")

    target = ToolRegistry()
    target.register(original)
    old_copy = target.copy()

    source = ToolRegistry()
    source.register(replacement)

    target.replace_with(source)
    new_copy = target.copy()

    assert tuple(tool.tool_id for tool in old_copy.definitions()) == ("builtin.echo",)
    assert tuple(tool.tool_id for tool in target.definitions()) == (
        "builtin.calculator",
    )
    assert tuple(tool.tool_id for tool in new_copy.definitions()) == (
        "builtin.calculator",
    )
