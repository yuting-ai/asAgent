import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence

import httpx

from asagent.models.config import ProviderAdapter, ProviderConfig
from asagent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.errors import (
    ProviderAuthenticationError,
    ProviderBillingError,
    ProviderConfigurationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderServiceError,
    ProviderTimeoutError,
    ProviderTransportError,
)
from asagent.models.secrets import SecretProvider


class OpenAICompatibleProvider:
    """Maps asAgent's provider-neutral contracts to Chat Completions HTTP."""

    def __init__(
        self,
        *,
        config: ProviderConfig,
        secrets: SecretProvider,
        http_client: httpx.AsyncClient,
        retry_delay_seconds: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if config.adapter is not ProviderAdapter.OPENAI_COMPATIBLE:
            raise ProviderConfigurationError(
                "OpenAICompatibleProvider requires openai_compatible config",
            )

        self._config = config
        self._secrets = secrets
        self._http_client = http_client
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep

    async def complete(self, request: ModelRequest) -> ModelResponse:
        for attempt in range(2):
            try:
                response = await self._post(request, stream=False)
                return self._parse_response(response.json())
            except (json.JSONDecodeError, ValueError) as error:
                raise ProviderResponseError(
                    "model provider returned an invalid completion response",
                ) from error
            except ProviderError as error:
                if not error.retryable or attempt == 1:
                    raise

                await self._sleep(self._retry_delay_seconds)

        raise AssertionError("unreachable")

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        try:
            async with self._http_client.stream(
                "POST",
                self._endpoint(),
                headers=self._headers(),
                json=self._payload(request, stream=True),
                timeout=self._config.timeout_seconds,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue

                    data = line.removeprefix("data:").strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        return

                    try:
                        chunk = self._as_mapping(
                            json.loads(data),
                            "stream response chunk",
                        )
                        events = self._parse_stream_chunk(chunk)
                    except (json.JSONDecodeError, ValueError) as error:
                        raise ProviderResponseError(
                            "model provider returned an invalid stream response",
                        ) from error

                    for event in events:
                        yield event
        except httpx.HTTPStatusError as error:
            raise self._error_from_status(error.response.status_code) from error
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(
                "model provider request timed out",
            ) from error
        except httpx.RequestError as error:
            raise ProviderTransportError(
                "model provider transport request failed",
            ) from error

    async def _post(
        self,
        request: ModelRequest,
        *,
        stream: bool,
    ) -> httpx.Response:
        try:
            response = await self._http_client.post(
                self._endpoint(),
                headers=self._headers(),
                json=self._payload(request, stream=stream),
                timeout=self._config.timeout_seconds,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            raise self._error_from_status(error.response.status_code) from error
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(
                "model provider request timed out",
            ) from error
        except httpx.RequestError as error:
            raise ProviderTransportError(
                "model provider transport request failed",
            ) from error

    def _endpoint(self) -> str:
        return f"{str(self._config.base_url).rstrip('/')}/chat/completions"

    def _headers(self) -> dict[str, str]:
        secret = self._secrets.get_secret(self._config.secret_id)
        if not secret:
            raise ProviderConfigurationError(
                "model provider secret is unavailable",
            )

        return {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        }

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, object]:
        messages: list[dict[str, object]] = []

        if request.system_prompt:
            messages.append(
                {
                    "role": ModelMessageRole.SYSTEM.value,
                    "content": request.system_prompt,
                }
            )

        for message in request.messages:
            messages.append(self._message_payload(message))

        if not messages:
            raise ValueError("a model request must contain at least one message")

        payload: dict[str, object] = {
            "model": request.model,
            "messages": messages,
            "stream": stream,
        }

        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.input_schema),
                    },
                }
                for tool in request.tools
            ]

        return payload

    def _message_payload(self, message: ModelMessage) -> dict[str, object]:
        payload: dict[str, object] = {
            "role": message.role.value,
            "content": message.content,
        }

        if message.role is ModelMessageRole.ASSISTANT and message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": tool_call.call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(dict(tool_call.arguments)),
                    },
                }
                for tool_call in message.tool_calls
            ]

        if message.role is ModelMessageRole.TOOL:
            if message.tool_call_id is None:
                raise AssertionError("validated tool message has no tool_call_id")
            payload["tool_call_id"] = message.tool_call_id

        return payload

    def _parse_response(self, response: object) -> ModelResponse:
        data = self._as_mapping(response, "completion response")
        choices = self._as_sequence(data.get("choices"), "completion choices")
        if not choices:
            raise ValueError("completion response must contain a choice")

        choice = self._as_mapping(choices[0], "completion choice")
        message = self._as_mapping(choice.get("message"), "completion message")
        tool_calls = self._parse_tool_calls(message.get("tool_calls"))

        usage = data.get("usage")
        usage_data = None if usage is None else self._as_mapping(usage, "usage")

        return ModelResponse(
            text=self._optional_string(message.get("content"), "message content"),
            tool_calls=tool_calls,
            input_tokens=(
                None
                if usage_data is None
                else self._optional_int(
                    usage_data.get("prompt_tokens"),
                    "prompt_tokens",
                )
            ),
            output_tokens=(
                None
                if usage_data is None
                else self._optional_int(
                    usage_data.get("completion_tokens"),
                    "completion_tokens",
                )
            ),
            reasoning=self._optional_string(
                message.get("reasoning_content"),
                "reasoning_content",
            ),
        )

    def _parse_stream_chunk(
        self,
        chunk: Mapping[str, object],
    ) -> tuple[ModelEvent, ...]:
        choices = self._as_sequence(chunk.get("choices"), "stream choices")
        events: list[ModelEvent] = []

        for raw_choice in choices:
            choice = self._as_mapping(raw_choice, "stream choice")
            delta = self._as_mapping(choice.get("delta"), "stream delta")

            if "tool_calls" in delta:
                raise NotImplementedError(
                    "streaming tool calls require the later Agent Loop",
                )

            text = self._optional_string(delta.get("content"), "stream content")
            if text:
                events.append(
                    ModelEvent(
                        event_type="text.delta",
                        text_delta=text,
                    )
                )

            reasoning = self._optional_string(
                delta.get("reasoning_content"),
                "stream reasoning_content",
            )
            if reasoning:
                events.append(
                    ModelEvent(
                        event_type="reasoning.delta",
                        reasoning_delta=reasoning,
                    )
                )

        return tuple(events)

    def _parse_tool_calls(self, value: object) -> tuple[ModelToolCall, ...]:
        if value is None:
            return ()

        return tuple(
            self._parse_tool_call(raw_tool_call)
            for raw_tool_call in self._as_sequence(value, "tool_calls")
        )

    def _parse_tool_call(self, value: object) -> ModelToolCall:
        tool_call = self._as_mapping(value, "tool call")
        function = self._as_mapping(tool_call.get("function"), "tool call function")
        arguments_text = self._required_string(
            function.get("arguments"),
            "tool call arguments",
        )
        arguments = self._as_mapping(
            json.loads(arguments_text),
            "tool call arguments JSON",
        )

        return ModelToolCall(
            call_id=self._required_string(tool_call.get("id"), "tool call id"),
            name=self._required_string(function.get("name"), "tool call name"),
            arguments=dict(arguments),
        )

    @staticmethod
    def _error_from_status(status_code: int) -> ProviderError:
        if status_code == 401:
            return ProviderAuthenticationError(
                "model provider authentication failed",
                status_code=status_code,
            )
        if status_code == 402:
            return ProviderBillingError(
                "model provider account has insufficient balance",
                status_code=status_code,
            )
        if status_code in {400, 422}:
            return ProviderRequestError(
                "model provider rejected the request",
                status_code=status_code,
            )
        if status_code == 429:
            return ProviderRateLimitError(
                "model provider rate limit reached",
                status_code=status_code,
            )
        if status_code >= 500:
            return ProviderServiceError(
                "model provider service failed",
                status_code=status_code,
            )

        return ProviderRequestError(
            "model provider request failed",
            status_code=status_code,
        )

    @staticmethod
    def _as_mapping(value: object, description: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{description} must be an object")

        return value

    @staticmethod
    def _as_sequence(value: object, description: str) -> Sequence[object]:
        if not isinstance(value, list):
            raise ValueError(f"{description} must be a list")

        return value

    @staticmethod
    def _optional_string(value: object, description: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{description} must be a string or null")
        return value

    @staticmethod
    def _required_string(value: object, description: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{description} must be a non-empty string")
        return value

    @staticmethod
    def _optional_int(value: object, description: str) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{description} must be an integer or null")
        return value
