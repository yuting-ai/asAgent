import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from asagent.models.contracts import (
    ModelMessage,
    ModelRequest,
    ModelToolDefinition,
)


@dataclass(frozen=True, slots=True)
class ModelContextCapabilities:
    """The hard context-window limit declared by a model configuration."""

    context_window_tokens: int

    def __post_init__(self) -> None:
        if self.context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be positive")


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """The user-selected input and output policy for one model request."""

    max_input_tokens: int
    reserved_output_tokens: int

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive")
        if self.reserved_output_tokens <= 0:
            raise ValueError("reserved_output_tokens must be positive")

    def resolve(
        self,
        capabilities: ModelContextCapabilities,
    ) -> "ResolvedContextBudget":
        available_input_tokens = (
            capabilities.context_window_tokens - self.reserved_output_tokens
        )
        if available_input_tokens <= 0:
            raise ValueError(
                "reserved_output_tokens must be smaller than context_window_tokens",
            )

        return ResolvedContextBudget(
            context_window_tokens=capabilities.context_window_tokens,
            requested_input_tokens=self.max_input_tokens,
            reserved_output_tokens=self.reserved_output_tokens,
            input_budget_tokens=min(
                self.max_input_tokens,
                available_input_tokens,
            ),
        )


@dataclass(frozen=True, slots=True)
class ResolvedContextBudget:
    """The effective input limit after applying model and user constraints."""

    context_window_tokens: int
    requested_input_tokens: int
    reserved_output_tokens: int
    input_budget_tokens: int

    def __post_init__(self) -> None:
        if self.context_window_tokens <= 0:
            raise ValueError("context_window_tokens must be positive")
        if self.requested_input_tokens <= 0:
            raise ValueError("requested_input_tokens must be positive")
        if self.reserved_output_tokens <= 0:
            raise ValueError("reserved_output_tokens must be positive")
        if self.input_budget_tokens <= 0:
            raise ValueError("input_budget_tokens must be positive")
        if (
            self.input_budget_tokens + self.reserved_output_tokens
            > self.context_window_tokens
        ):
            raise ValueError(
                "input_budget_tokens and reserved_output_tokens exceed "
                "context_window_tokens",
            )


@runtime_checkable
class TokenEstimator(Protocol):
    """Estimates the input cost of provider-neutral model request components."""

    def estimate_system_prompt(self, system_prompt: str) -> int: ...

    def estimate_message(self, message: ModelMessage) -> int: ...

    def estimate_tool_definition(self, tool: ModelToolDefinition) -> int: ...


class ConservativeUtf8TokenEstimator:
    """A deterministic upper-bound-style estimate until a Provider tokenizer exists."""

    _MESSAGE_OVERHEAD_TOKENS = 4
    _TOOL_CALL_OVERHEAD_TOKENS = 8
    _TOOL_DEFINITION_OVERHEAD_TOKENS = 8

    def estimate_system_prompt(self, system_prompt: str) -> int:
        return self._MESSAGE_OVERHEAD_TOKENS + self._estimate_text(system_prompt)

    def estimate_message(self, message: ModelMessage) -> int:
        tokens = self._MESSAGE_OVERHEAD_TOKENS

        if message.content is not None:
            tokens += self._estimate_text(message.content)
        if message.tool_call_id is not None:
            tokens += self._estimate_text(message.tool_call_id)

        for tool_call in message.tool_calls:
            tokens += self._TOOL_CALL_OVERHEAD_TOKENS
            tokens += self._estimate_text(tool_call.call_id)
            tokens += self._estimate_text(tool_call.name)
            tokens += self._estimate_text(
                self._canonical_json(dict(tool_call.arguments)),
            )

        return tokens

    def estimate_tool_definition(self, tool: ModelToolDefinition) -> int:
        return (
            self._TOOL_DEFINITION_OVERHEAD_TOKENS
            + self._estimate_text(tool.name)
            + self._estimate_text(tool.description)
            + self._estimate_text(
                self._canonical_json(dict(tool.input_schema)),
            )
        )

    @staticmethod
    def _estimate_text(text: str) -> int:
        return len(text.encode("utf-8"))

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class ContextUsage:
    """An immutable accounting snapshot for one prospective model request."""

    budget: ResolvedContextBudget
    system_prompt_tokens: int
    tool_schema_tokens: int
    message_tokens: int

    def __post_init__(self) -> None:
        if self.system_prompt_tokens < 0:
            raise ValueError("system_prompt_tokens must not be negative")
        if self.tool_schema_tokens < 0:
            raise ValueError("tool_schema_tokens must not be negative")
        if self.message_tokens < 0:
            raise ValueError("message_tokens must not be negative")

    @classmethod
    def from_request(
        cls,
        *,
        request: ModelRequest,
        budget: ResolvedContextBudget,
        estimator: TokenEstimator,
    ) -> "ContextUsage":
        return cls(
            budget=budget,
            system_prompt_tokens=estimator.estimate_system_prompt(
                request.system_prompt,
            ),
            tool_schema_tokens=sum(
                estimator.estimate_tool_definition(tool) for tool in request.tools
            ),
            message_tokens=sum(
                estimator.estimate_message(message) for message in request.messages
            ),
        )

    @property
    def input_tokens(self) -> int:
        return self.system_prompt_tokens + self.tool_schema_tokens + self.message_tokens

    @property
    def remaining_input_tokens(self) -> int:
        return self.budget.input_budget_tokens - self.input_tokens

    @property
    def is_within_budget(self) -> bool:
        return self.remaining_input_tokens >= 0
