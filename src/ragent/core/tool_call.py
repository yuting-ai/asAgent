from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from ragent.core.ids import RunId, ToolCallId


@dataclass(frozen=True, slots=True)
class ToolCall:
    tool_call_id: ToolCallId
    run_id: RunId
    tool_id: str
    arguments: Mapping[str, object]
    result: str | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if self.result is not None and self.error is not None:
            raise ValueError("result and error cannot both be set")

        object.__setattr__(
            self,
            "arguments",
            MappingProxyType(dict(self.arguments)),
        )
