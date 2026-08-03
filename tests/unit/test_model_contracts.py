from dataclasses import FrozenInstanceError

import pytest

from ragent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
    ModelToolDefinition,
)


def test_model_request_preserves_provider_neutral_input() -> None:
    input_schema = {"type": "object"}
    tool = ModelToolDefinition(
        name="calculator",
        description="Evaluate an arithmetic expression.",
        input_schema=input_schema,
    )
    request = ModelRequest(
        model="fake-model",
        system_prompt="You are a helpful assistant.",
        messages=(
            ModelMessage(
                role=ModelMessageRole.USER,
                content="What is 2 + 2?",
            ),
        ),
        tools=(tool,),
    )

    assert request.model == "fake-model"
    assert request.system_prompt == "You are a helpful assistant."
    assert request.messages[0].role is ModelMessageRole.USER
    assert request.messages[0].content == "What is 2 + 2?"
    assert request.tools[0].name == "calculator"

    input_schema["type"] = "array"
    assert tool.input_schema == {"type": "object"}


def test_model_response_can_contain_provider_tool_calls() -> None:
    arguments = {"expression": "2 + 2"}
    tool_call = ModelToolCall(
        call_id="provider_call_123",
        name="calculator",
        arguments=arguments,
    )
    response = ModelResponse(
        text=None,
        tool_calls=(tool_call,),
        input_tokens=12,
        output_tokens=3,
        reasoning=None,
    )

    assert response.text is None
    assert response.tool_calls[0].call_id == "provider_call_123"
    assert response.tool_calls[0].name == "calculator"
    assert response.tool_calls[0].arguments == {"expression": "2 + 2"}
    assert response.input_tokens == 12
    assert response.output_tokens == 3

    arguments["expression"] = "changed"
    assert response.tool_calls[0].arguments == {"expression": "2 + 2"}


def test_model_event_represents_streaming_deltas_and_tool_calls() -> None:
    text_event = ModelEvent(
        event_type="text.delta",
        text_delta="Hello",
    )
    tool_event = ModelEvent(
        event_type="tool.call",
        tool_call=ModelToolCall(
            call_id="provider_call_123",
            name="calculator",
            arguments={"expression": "2 + 2"},
        ),
    )

    assert text_event.text_delta == "Hello"
    assert text_event.tool_call is None
    assert tool_event.text_delta is None
    assert tool_event.tool_call is not None
    assert tool_event.tool_call.name == "calculator"


def test_model_contracts_are_immutable() -> None:
    request = ModelRequest(
        model="fake-model",
        system_prompt="You are a helpful assistant.",
        messages=(),
        tools=(),
    )

    with pytest.raises(FrozenInstanceError):
        request.model = "other-model"  # type: ignore[misc]
