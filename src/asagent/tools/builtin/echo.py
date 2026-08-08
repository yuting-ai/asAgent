from collections.abc import Mapping

from asagent.core.tool_definition import ToolDefinition


class EchoTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.echo",
            display_name="Echo",
            description="Returns the supplied text unchanged with an Echo prefix.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to echo.",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        return f"Echo: {arguments['text']}"
