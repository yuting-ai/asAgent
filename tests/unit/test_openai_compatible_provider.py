import json

import httpx
import pytest

from asagent.models.config import ProviderConfig
from asagent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelToolCall,
    ModelToolDefinition,
)
from asagent.models.errors import (
    ProviderAuthenticationError,
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderTransportError,
)
from asagent.models.openai_compatible_provider import OpenAICompatibleProvider
from asagent.models.provider import ModelProvider


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

        with pytest.raises(
            ProviderConfigurationError,
            match="secret is unavailable",
        ):
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


@pytest.mark.asyncio
async def test_complete_retries_rate_limit_once() -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1

        if calls == 1:
            return httpx.Response(429)

        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Recovered."}}],
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 2,
                },
            },
        )

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as client:
        provider = OpenAICompatibleProvider(
            config=make_config(),
            secrets=InMemorySecretProvider(
                {"deepseek_api_key": "value-from-secret-store"},
            ),
            http_client=client,
            sleep=record_sleep,
        )

        response = await provider.complete(make_request())

    assert response.text == "Recovered."
    assert calls == 2
    assert delays == [0.5]


@pytest.mark.asyncio
async def test_complete_does_not_retry_authentication_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

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

        with pytest.raises(ProviderAuthenticationError) as error:
            await provider.complete(make_request())

    assert error.value.status_code == 401
    assert error.value.retryable is False
    assert calls == 1


@pytest.mark.asyncio
async def test_complete_does_not_retry_ambiguous_transport_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("connection failed", request=request)

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

        with pytest.raises(ProviderTransportError) as error:
            await provider.complete(make_request())

    assert error.value.retryable is False
    assert calls == 1


@pytest.mark.asyncio
async def test_complete_wraps_invalid_json_without_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="not-json")

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

        with pytest.raises(ProviderResponseError) as error:
            await provider.complete(make_request())

    assert str(error.value) == "model provider returned an invalid completion response"


@pytest.mark.asyncio
async def test_complete_maps_tool_call_history_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["messages"] == [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is 2 + 2?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "calculator",
                            "arguments": '{"expression": "2 + 2"}',
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "content": "4",
                "tool_call_id": "call_123",
            },
        ]

        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "The result is 4."}}]},
        )

    request = ModelRequest(
        model="deepseek-test",
        system_prompt="Be concise.",
        messages=(
            ModelMessage(
                role=ModelMessageRole.USER,
                content="What is 2 + 2?",
            ),
            ModelMessage(
                role=ModelMessageRole.ASSISTANT,
                content=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="calculator",
                        arguments={"expression": "2 + 2"},
                    ),
                ),
            ),
            ModelMessage(
                role=ModelMessageRole.TOOL,
                content="4",
                tool_call_id="call_123",
            ),
        ),
        tools=(),
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

        response = await provider.complete(request)

    assert response.text == "The result is 4."
    assert response.tool_calls == ()
