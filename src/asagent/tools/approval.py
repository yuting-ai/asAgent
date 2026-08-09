from collections.abc import Mapping
from typing import Protocol

from asagent.core.tool_definition import ToolDefinition


class ToolApprovalPolicy(Protocol):
    async def approve(
        self,
        definition: ToolDefinition,
        arguments: Mapping[str, object],
    ) -> bool: ...
