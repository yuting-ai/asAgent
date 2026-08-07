import json

import httpx
import pytest

from ragent.models.config import ProviderConfig
from ragent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelToolDefinition,
)
from ragent.models.openai_compatible_provider import OpenAICompatibleProvider
from ragent.models.provider import ModelProvider


class InMemorySecretProvider:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets

    def get_secret(self, secret_id: str) -> str | None:
        return self._secrets.get(secret_id)


def make_config() -> ProviderConfig:
    return ProviderConfig.model_validate(
        {
            "adapter": "openai_compatible",
            "model": "deepseek-test",
            "base_url": "https://api.example.test/v1",
            "secret_id": "deepseek_api_key",
            "timeout_seconds": 12,
        }
    )


def make_request() -> ModelRequest:
    return ModelRequest(
        model="deepseek-test",
        system_prompt="Be concise.",
        messages=(
            ModelMessage(
                role=ModelMessageRole.USER,
                content="What is two plus two?",
            ),
            ModelMessage(
                role=ModelMessageRole.ASSISTANT,
                content="Let me calculate.",
            ),
        ),
        tools=(
            ModelToolDefinition(
                name="calculator",
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


@pytest.mark.asyncio
async def test_complete_maps_request_and_response_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer value-from-secret-store"

        assert json.loads(request.content) == {
            "model": "deepseek-test",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "What is two plus two?"},
                {"role": "assistant", "content": "Let me calculate."},
            ],
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": "Evaluate arithmetic.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "expression": {"type": "string"},
                            },
                        },
                    },
                },
            ],
        }

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Four.",
                            "reasoning_content": "2 + 2 equals 4.",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":"2 + 2"}',
                                    },
                                },
                            ],
                        },
                    },
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider: ModelProvider = OpenAICompatibleProvider(
            config=make_config(),
            secrets=InMemorySecretProvider(
                {"deepseek_api_key": "value-from-secret-store"},
            ),
            http_client=client,
        )

        response = await provider.complete(make_request())

    assert isinstance(provider, ModelProvider)
    assert response.text == "Four."
    assert response.reasoning == "2 + 2 equals 4."
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.tool_calls[0].call_id == "call_123"
    assert response.tool_calls[0].name == "calculator"
    assert response.tool_calls[0].arguments == {"expression": "2 + 2"}


@pytest.mark.asyncio
async def test_stream_maps_text_and_reasoning_events_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True

        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                'data: {"choices":[{"delta":{"reasoning_content":"First"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"Answer"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = OpenAICompatibleProvider(
            config=make_config(),
            secrets=InMemorySecretProvider(
                {"deepseek_api_key": "value-from-secret-store"},
            ),
            http_client=client,
        )

        events = [event async for event in provider.stream(make_request())]

    assert events == [
        ModelEvent(
            event_type="reasoning.delta",
            reasoning_delta="First",
        ),
        ModelEvent(
            event_type="text.delta",
            text_delta="Answer",
        ),
    ]


@pytest.mark.asyncio
async def test_complete_rejects_missing_secret_before_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not run when the secret is missing")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = OpenAICompatibleProvider(
            config=make_config(),
            secrets=InMemorySecretProvider({}),
            http_client=client,
        )

        with pytest.raises(ValueError, match="secret is unavailable"):
            await provider.complete(make_request())


@pytest.mark.asyncio
async def test_stream_rejects_tool_call_chunks_until_agent_loop_exists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=(
                'data: {"choices":[{"delta":{"tool_calls":[]}}]}\n\ndata: [DONE]\n\n'
            ),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = OpenAICompatibleProvider(
            config=make_config(),
            secrets=InMemorySecretProvider(
                {"deepseek_api_key": "value-from-secret-store"},
            ),
            http_client=client,
        )

        with pytest.raises(
            NotImplementedError,
            match="streaming tool calls",
        ):
            _events: list[ModelEvent] = [
                event async for event in provider.stream(make_request())
            ]
