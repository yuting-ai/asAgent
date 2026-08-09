import asyncio
from collections.abc import Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from asagent.core.tool import Tool
from asagent.tools.errors import ToolArgumentsValidationError, ToolTimeoutError
from asagent.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> str:
        tool: Tool = self._registry.get(tool_id)

        try:
            Draft202012Validator(tool.definition.input_schema).validate(
                dict(arguments),
            )
        except ValidationError as error:
            raise ToolArgumentsValidationError(
                "tool arguments are invalid",
            ) from error

        try:
            return await asyncio.wait_for(
                tool.execute(arguments),
                timeout=tool.definition.timeout_seconds,
            )
        except TimeoutError as error:
            raise ToolTimeoutError("tool execution timed out") from error
