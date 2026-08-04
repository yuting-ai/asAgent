from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ragent.core.tool_definition import ToolDefinition


@runtime_checkable
class Tool(Protocol):
    @property
    def definition(self) -> ToolDefinition: ...

    async def execute(self, arguments: Mapping[str, object]) -> str: ...
