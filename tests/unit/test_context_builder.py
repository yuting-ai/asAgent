from dataclasses import FrozenInstanceError

import pytest

from asagent.agent.context_budget import (
    ConservativeUtf8TokenEstimator,
    ContextBudget,
    ModelContextCapabilities,
    ResolvedContextBudget,
)
from asagent.agent.context_builder import (
    ContextBudgetExceededError,
    ContextBuilder,
)
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelToolCall,
    ModelToolDefinition,
)


def _budget(input_budget_tokens: int) -> ResolvedContextBudget:
    return ContextBudget(
        max_input_tokens=input_budget_tokens,
        reserved_output_tokens=1,
    ).resolve(
        ModelContextCapabilities(
            context_window_tokens=input_budget_tokens + 1,
        ),
    )


def _user(content: str) -> ModelMessage:
    return ModelMessage(role=ModelMessageRole.USER, content=content)


def _assistant(content: str) -> ModelMessage:
    return ModelMessage(role=ModelMessageRole.ASSISTANT, content=content)


def _tool_call(call_id: str) -> ModelToolCall:
    return ModelToolCall(
        call_id=call_id,
        name="builtin_calculator",
        arguments={"expression": "2 + 2"},
    )


def _assistant_tool_call(call_id: str) -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.ASSISTANT,
        content=None,
        tool_calls=(_tool_call(call_id),),
    )


def _tool_result(call_id: str) -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.TOOL,
        content="4",
        tool_call_id=call_id,
    )


def _tool_definition() -> ModelToolDefinition:
    return ModelToolDefinition(
        name="builtin_calculator",
        description="Evaluate arithmetic.",
        input_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string"},
            },
        },
    )


def _message_tokens(messages: tuple[ModelMessage, ...]) -> int:
    estimator = ConservativeUtf8TokenEstimator()
    return sum(estimator.estimate_message(message) for message in messages)


def test_builder_selects_recent_complete_history_after_fixed_costs() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    system_prompt = "Use tools when useful."
    tools = (_tool_definition(),)
    old_history = (
        _user("old question"),
        _assistant("old answer"),
    )
    recent_history = (
        _user("calculate 2 + 2"),
        _assistant_tool_call("call-1"),
        _tool_result("call-1"),
        _assistant("The answer is 4."),
    )
    fixed_tokens = estimator.estimate_system_prompt(system_prompt) + sum(
        estimator.estimate_tool_definition(tool) for tool in tools
    )
    builder = ContextBuilder(
        budget=_budget(fixed_tokens + _message_tokens(recent_history)),
        estimator=estimator,
    )

    snapshot = builder.build(
        model="test-model",
        system_prompt=system_prompt,
        history=old_history + recent_history,
        tools=tools,
    )

    assert snapshot.request.model == "test-model"
    assert snapshot.request.system_prompt == system_prompt
    assert snapshot.request.tools == tools
    assert snapshot.request.messages == recent_history
    assert snapshot.history_selection.messages == recent_history
    assert snapshot.history_selection.omitted_unit_count == 1
    assert snapshot.usage.is_within_budget is True
    assert snapshot.usage.remaining_input_tokens == 0


def test_builder_preserves_a_complete_tool_call_chain() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    history = (
        _user("calculate 2 + 2"),
        _assistant_tool_call("call-1"),
        _tool_result("call-1"),
        _assistant("The answer is 4."),
    )
    system_prompt = "system"
    fixed_tokens = estimator.estimate_system_prompt(system_prompt)
    builder = ContextBuilder(
        budget=_budget(fixed_tokens + _message_tokens(history)),
        estimator=estimator,
    )

    snapshot = builder.build(
        model="test-model",
        system_prompt=system_prompt,
        history=history,
        tools=(),
    )

    assert snapshot.request.messages == history
    assert snapshot.history_selection.omitted_unit_count == 0


def test_builder_rejects_fixed_costs_that_exceed_the_budget() -> None:
    builder = ContextBuilder(
        budget=_budget(1),
        estimator=ConservativeUtf8TokenEstimator(),
    )

    with pytest.raises(ContextBudgetExceededError, match="system prompt"):
        builder.build(
            model="test-model",
            system_prompt="system",
            history=(),
            tools=(),
        )


def test_builder_rejects_a_latest_history_unit_that_does_not_fit() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    system_prompt = "system"
    history = (_user("this message is too large for the remaining budget"),)
    fixed_tokens = estimator.estimate_system_prompt(system_prompt)
    builder = ContextBuilder(
        budget=_budget(fixed_tokens + _message_tokens(history) - 1),
        estimator=estimator,
    )

    with pytest.raises(ContextBudgetExceededError, match="latest complete"):
        builder.build(
            model="test-model",
            system_prompt=system_prompt,
            history=history,
            tools=(),
        )


def test_builder_supports_empty_history_when_fixed_costs_fit() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    system_prompt = "system"
    fixed_tokens = estimator.estimate_system_prompt(system_prompt)
    builder = ContextBuilder(
        budget=_budget(fixed_tokens),
        estimator=estimator,
    )

    snapshot = builder.build(
        model="test-model",
        system_prompt=system_prompt,
        history=(),
        tools=(),
    )

    assert snapshot.request.messages == ()
    assert snapshot.history_selection.omitted_unit_count == 0
    assert snapshot.usage.is_within_budget is True


def test_snapshot_is_immutable() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    system_prompt = "system"
    builder = ContextBuilder(
        budget=_budget(estimator.estimate_system_prompt(system_prompt)),
        estimator=estimator,
    )
    snapshot = builder.build(
        model="test-model",
        system_prompt=system_prompt,
        history=(),
        tools=(),
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.budget = _budget(1)  # type: ignore[misc]
