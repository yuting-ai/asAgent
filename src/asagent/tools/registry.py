from asagent.core.tool import Tool
from asagent.core.tool_definition import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        tool_id = tool.definition.tool_id
        if tool_id in self._tools:
            raise ValueError(f"tool_id is already registered: {tool_id}")

        self._tools[tool_id] = tool

    def get(self, tool_id: str) -> Tool:
        try:
            return self._tools[tool_id]
        except KeyError as error:
            raise KeyError(f"tool_id is not registered: {tool_id}") from error

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())
