from dataclasses import FrozenInstanceError

import pytest

from asagent.agent.context_budget import (
    ConservativeUtf8TokenEstimator,
    ContextBudget,
    ContextUsage,
    ModelContextCapabilities,
    TokenEstimator,
)
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelToolCall,
    ModelToolDefinition,
)


def _budget() -> ContextBudget:
    return ContextBudget(
        max_input_tokens=800,
        reserved_output_tokens=300,
    )


def test_budget_uses_the_smaller_of_user_and_model_input_limits() -> None:
    resolved = _budget().resolve(
        ModelContextCapabilities(context_window_tokens=1_000),
    )

    assert resolved.context_window_tokens == 1_000
    assert resolved.requested_input_tokens == 800
    assert resolved.reserved_output_tokens == 300
    assert resolved.input_budget_tokens == 700


def test_budget_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="context_window_tokens"):
        ModelContextCapabilities(context_window_tokens=0)

    with pytest.raises(ValueError, match="max_input_tokens"):
        ContextBudget(max_input_tokens=0, reserved_output_tokens=1)

    with pytest.raises(ValueError, match="reserved_output_tokens"):
        ContextBudget(max_input_tokens=1, reserved_output_tokens=0)


def test_budget_rejects_an_output_reserve_that_consumes_the_window() -> None:
    with pytest.raises(ValueError, match="smaller"):
        ContextBudget(
            max_input_tokens=1,
            reserved_output_tokens=100,
        ).resolve(ModelContextCapabilities(context_window_tokens=100))


def test_estimator_is_a_token_estimator_and_counts_utf8_deterministically() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    protocol: TokenEstimator = estimator

    assert isinstance(protocol, TokenEstimator)
    assert estimator.estimate_system_prompt("hello") == 9
    assert estimator.estimate_system_prompt("你好") == 10


def test_context_usage_accounts_for_system_tools_messages_and_tool_calls() -> None:
    estimator = ConservativeUtf8TokenEstimator()
    tool_call = ModelToolCall(
        call_id="call-1",
        name="builtin_calculator",
        arguments={"expression": "2 + 2"},
    )
    request = ModelRequest(
        model="test-model",
        system_prompt="Use tools when useful.",
        messages=(
            ModelMessage(
                role=ModelMessageRole.USER,
                content="calculate 2 + 2",
            ),
            ModelMessage(
                role=ModelMessageRole.ASSISTANT,
                content=None,
                tool_calls=(tool_call,),
            ),
            ModelMessage(
                role=ModelMessageRole.TOOL,
                content="4",
                tool_call_id="call-1",
            ),
        ),
        tools=(
            ModelToolDefinition(
                name="builtin_calculator",
                description="Evaluate arithmetic.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string"},
                    },
                },
            ),
        ),
    )
    budget = ContextBudget(
        max_input_tokens=300,
        reserved_output_tokens=50,
    ).resolve(ModelContextCapabilities(context_window_tokens=500))

    usage = ContextUsage.from_request(
        request=request,
        budget=budget,
        estimator=estimator,
    )

    assert usage.system_prompt_tokens == estimator.estimate_system_prompt(
        request.system_prompt,
    )
    assert usage.tool_schema_tokens == sum(
        estimator.estimate_tool_definition(tool) for tool in request.tools
    )
    assert usage.message_tokens == sum(
        estimator.estimate_message(message) for message in request.messages
    )
    assert usage.input_tokens == (
        usage.system_prompt_tokens + usage.tool_schema_tokens + usage.message_tokens
    )
    assert usage.remaining_input_tokens == (
        budget.input_budget_tokens - usage.input_tokens
    )
    assert usage.is_within_budget is True


def test_context_usage_reports_over_budget_without_mutating_the_snapshot() -> None:
    request = ModelRequest(
        model="test-model",
        system_prompt="system",
        messages=(
            ModelMessage(
                role=ModelMessageRole.USER,
                content="x" * 100,
            ),
        ),
        tools=(),
    )
    budget = ContextBudget(
        max_input_tokens=10,
        reserved_output_tokens=10,
    ).resolve(ModelContextCapabilities(context_window_tokens=100))
    usage = ContextUsage.from_request(
        request=request,
        budget=budget,
        estimator=ConservativeUtf8TokenEstimator(),
    )

    assert usage.remaining_input_tokens < 0
    assert usage.is_within_budget is False

    with pytest.raises(FrozenInstanceError):
        usage.message_tokens = 0  # type: ignore[misc]
