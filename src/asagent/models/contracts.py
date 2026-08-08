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
class ModelMessage:
    role: ModelMessageRole
    content: str | None
    tool_calls: tuple[ModelToolCall, ...] = ()
    tool_call_id: str | None = None

    def __post_init__(self) -> None:
        if self.role is ModelMessageRole.TOOL:
            if self.content is None:
                raise ValueError("tool messages require content")
            if self.tool_call_id is None:
                raise ValueError("tool messages require tool_call_id")
            if self.tool_calls:
                raise ValueError("tool messages cannot contain tool_calls")
            return

        if self.tool_call_id is not None:
            raise ValueError("only tool messages can contain tool_call_id")

        if self.role is not ModelMessageRole.ASSISTANT and self.tool_calls:
            raise ValueError("only assistant messages can contain tool_calls")


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
