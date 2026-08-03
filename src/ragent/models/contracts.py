from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class ModelMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: ModelMessageRole
    content: str


@dataclass(frozen=True, slots=True)
class ModelToolDefinition:
    name: str
    description: str
    input_schema: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "input_schema",
            MappingProxyType(dict(self.input_schema)),
        )


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            MappingProxyType(dict(self.arguments)),
        )


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    system_prompt: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[ModelToolDefinition, ...]


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str | None
    tool_calls: tuple[ModelToolCall, ...]
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning: str | None = None


@dataclass(frozen=True, slots=True)
class ModelEvent:
    event_type: str
    text_delta: str | None = None
    reasoning_delta: str | None = None
    tool_call: ModelToolCall | None = None
