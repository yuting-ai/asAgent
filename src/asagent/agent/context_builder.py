from dataclasses import dataclass

from asagent.agent.context_budget import (
    ContextUsage,
    ResolvedContextBudget,
    TokenEstimator,
)
from asagent.agent.context_history import (
    ContextHistorySelection,
    group_context_history,
    select_recent_context_history,
)
from asagent.models.contracts import (
    ModelMessage,
    ModelRequest,
    ModelToolDefinition,
)


class ContextBudgetExceededError(ValueError):
    """Raised when a valid model request cannot fit the configured input budget."""


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    """The immutable, complete input selected for one model request."""

    request: ModelRequest
    budget: ResolvedContextBudget
    usage: ContextUsage
    history_selection: ContextHistorySelection

    def __post_init__(self) -> None:
        if self.usage.budget != self.budget:
            raise ValueError("context snapshot usage must use its budget")
        if self.request.messages != self.history_selection.messages:
            raise ValueError(
                "context snapshot request messages must match the history selection",
            )
        if not self.usage.is_within_budget:
            raise ValueError("context snapshot request must fit its input budget")


class ContextBuilder:
    """Builds an immutable request from fixed context costs and complete history."""

    def __init__(
        self,
        *,
        budget: ResolvedContextBudget,
        estimator: TokenEstimator,
    ) -> None:
        self._budget = budget
        self._estimator = estimator

    def build(
        self,
        *,
        model: str,
        system_prompt: str,
        history: tuple[ModelMessage, ...],
        tools: tuple[ModelToolDefinition, ...],
    ) -> ContextSnapshot:
        fixed_input_tokens = self._estimate_fixed_input_tokens(
            system_prompt=system_prompt,
            tools=tools,
        )
        max_message_tokens = max(
            self._budget.input_budget_tokens - fixed_input_tokens,
            0,
        )
        history_selection = select_recent_context_history(
            units=group_context_history(history),
            max_message_tokens=max_message_tokens,
            estimator=self._estimator,
        )
        request = ModelRequest(
            model=model,
            system_prompt=system_prompt,
            messages=history_selection.messages,
            tools=tools,
        )
        usage = ContextUsage.from_request(
            request=request,
            budget=self._budget,
            estimator=self._estimator,
        )

        if fixed_input_tokens > self._budget.input_budget_tokens:
            raise ContextBudgetExceededError(
                "system prompt and tool definitions exceed the input budget",
            )
        if history and not history_selection.units:
            raise ContextBudgetExceededError(
                "the latest complete context history unit exceeds the input budget",
            )
        if not usage.is_within_budget:
            raise ContextBudgetExceededError(
                "the selected context exceeds the input budget",
            )

        return ContextSnapshot(
            request=request,
            budget=self._budget,
            usage=usage,
            history_selection=history_selection,
        )

    def _estimate_fixed_input_tokens(
        self,
        *,
        system_prompt: str,
        tools: tuple[ModelToolDefinition, ...],
    ) -> int:
        return self._estimator.estimate_system_prompt(system_prompt) + sum(
            self._estimator.estimate_tool_definition(tool) for tool in tools
        )
