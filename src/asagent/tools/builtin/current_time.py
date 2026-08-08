from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from asagent.core.tool_definition import ToolDefinition


def _utc_now() -> datetime:
    return datetime.now(UTC)


class CurrentTimeTool:
    def __init__(self, now: Callable[[], datetime] = _utc_now) -> None:
        self._now = now

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.current_time",
            display_name="Current time",
            description="Returns the current time in UTC using ISO 8601 format.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        current_time = self._now()
        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")

        return current_time.astimezone(UTC).isoformat()
