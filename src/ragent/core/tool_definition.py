from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    tool_id: str
    display_name: str
    description: str
    input_schema: Mapping[str, object]
    risk_level: str
    required_permissions: frozenset[str]
    requires_approval: bool
    timeout_seconds: float

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        object.__setattr__(
            self,
            "input_schema",
            MappingProxyType(dict(self.input_schema)),
        )
