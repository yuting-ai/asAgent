from collections.abc import AsyncIterator

import pytest

from asagent.models.contracts import (
    ModelEvent,
    ModelRequest,
    ModelResponse,
)
from asagent.models.provider import ModelProvider


class ExampleModelProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            text=f"Completed by {request.model}",
            tool_calls=(),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        yield ModelEvent(
            event_type="text.delta",
            text_delta=f"Streaming from {request.model}",
        )


def test_example_model_provider_satisfies_protocol() -> None:
    provider: ModelProvider = ExampleModelProvider()

    assert isinstance(provider, ModelProvider)


@pytest.mark.asyncio
async def test_model_provider_supports_complete_and_stream() -> None:
    provider: ModelProvider = ExampleModelProvider()
    request = ModelRequest(
        model="fake-model",
        system_prompt="You are a helpful assistant.",
        messages=(),
        tools=(),
    )

    response = await provider.complete(request)
    events = [event async for event in provider.stream(request)]

    assert response.text == "Completed by fake-model"
    assert response.tool_calls == ()
    assert events == [
        ModelEvent(
            event_type="text.delta",
            text_delta="Streaming from fake-model",
        ),
    ]
