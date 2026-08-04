import pytest

from ragent.models.contracts import (
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from ragent.models.fake_provider import FakeModelProvider
from ragent.models.provider import ModelProvider


def make_request() -> ModelRequest:
    return ModelRequest(
        model="fake-model",
        system_prompt="You are a helpful assistant.",
        messages=(),
        tools=(),
    )


@pytest.mark.asyncio
async def test_fake_provider_returns_scripted_text_and_tool_call() -> None:
    request = make_request()
    tool_call = ModelToolCall(
        call_id="provider_call_123",
        name="calculator",
        arguments={"expression": "2 + 2"},
    )
    fake = FakeModelProvider(
        responses=(
            ModelResponse(text="Hello, Ragent.", tool_calls=()),
            ModelResponse(text=None, tool_calls=(tool_call,)),
        ),
    )
    provider: ModelProvider = fake

    text_response = await provider.complete(request)
    tool_response = await provider.complete(request)

    assert isinstance(provider, ModelProvider)
    assert text_response.text == "Hello, Ragent."
    assert text_response.tool_calls == ()
    assert tool_response.text is None
    assert tool_response.tool_calls == (tool_call,)
    assert fake.requests == (request, request)


@pytest.mark.asyncio
async def test_fake_provider_returns_scripted_stream() -> None:
    request = make_request()
    fake = FakeModelProvider(
        streams=(
            (
                ModelEvent(event_type="text.delta", text_delta="Hello"),
                ModelEvent(event_type="text.delta", text_delta=", Ragent."),
            ),
        ),
    )
    provider: ModelProvider = fake

    events = [event async for event in provider.stream(request)]

    assert events == [
        ModelEvent(event_type="text.delta", text_delta="Hello"),
        ModelEvent(event_type="text.delta", text_delta=", Ragent."),
    ]
    assert fake.requests == (request,)


@pytest.mark.asyncio
async def test_fake_provider_rejects_unscripted_complete_calls() -> None:
    provider = FakeModelProvider()

    with pytest.raises(RuntimeError, match="no scripted response available"):
        await provider.complete(make_request())
