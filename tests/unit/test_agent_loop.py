import asyncio
from collections.abc import AsyncIterator, Callable, Mapping

import pytest

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.loop import AgentLoop
from asagent.core.ids import RunId
from asagent.core.run_status import RunStatus
from asagent.core.tool_definition import ToolDefinition
from asagent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.errors import ProviderTimeoutError
from asagent.models.fake_provider import FakeModelProvider
from asagent.models.provider import ModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot


class CountingEchoTool:
    def __init__(
        self,
        error: Exception | None = None,
        result: str = "Echo: hello",
        on_execute: Callable[[], None] | None = None,
        timeout_seconds: float = 1.0,
        required_permissions: frozenset[str] = frozenset(),
    ) -> None:
        self.calls = 0
        self._error = error
        self._result = result
        self._on_execute = on_execute
        self._definition = ToolDefinition(
            tool_id="builtin.echo",
            display_name="Echo",
            description="Returns supplied text.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "attempt": {"type": "integer"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=required_permissions,
            requires_approval=False,
            timeout_seconds=timeout_seconds,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(self, arguments: Mapping[str, object]) -> str:
        self.calls += 1
        assert arguments["text"] == "hello"
        if self._on_execute is not None:
            self._on_execute()
        if self._error is not None:
            raise self._error
        return self._result


class TimeoutModelProvider:
    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        raise ProviderTimeoutError("model provider request timed out")

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        raise AssertionError("stream is not used by AgentLoop")


class HangingEchoTool(CountingEchoTool):
    def __init__(self) -> None:
        super().__init__(timeout_seconds=0.01)

    async def execute(self, arguments: Mapping[str, object]) -> str:
        self.calls += 1
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


def _snapshot(tool: CountingEchoTool) -> ToolSnapshot:
    return ToolSnapshot.from_definitions(
        (tool.definition,),
        provider_name_for=openai_compatible_tool_name,
    )


def _loop(
    provider: ModelProvider,
    tool: CountingEchoTool,
    *,
    max_steps: int = 8,
    max_calls_per_tool_input: int | None = None,
    max_tool_result_chars: int = 4_000,
    granted_permissions: frozenset[str] = frozenset(),
) -> AgentLoop:
    registry = ToolRegistry()
    registry.register(tool)

    return AgentLoop(
        model=provider,
        executor=ToolExecutor(
            registry,
            granted_permissions=granted_permissions,
        ),
        tool_snapshot=_snapshot(tool),
        max_steps=max_steps,
        max_calls_per_tool_input=max_calls_per_tool_input,
        max_tool_result_chars=max_tool_result_chars,
    )


def _user_message() -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.USER,
        content="Please echo hello.",
    )


@pytest.mark.asyncio
async def test_loop_completes_after_a_text_response() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text="Hello!",
                tool_calls=(),
            ),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "Hello!"
    assert result.steps_used == 1
    assert result.messages[-1] == ModelMessage(
        role=ModelMessageRole.ASSISTANT,
        content="Hello!",
    )
    assert tool.calls == 0


@pytest.mark.asyncio
async def test_loop_executes_tool_then_returns_final_text() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(text="The tool said: Echo: hello", tool_calls=()),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "The tool said: Echo: hello"
    assert result.steps_used == 2
    assert tool.calls == 1
    assert provider.requests[1].messages[-2] == ModelMessage(
        role=ModelMessageRole.ASSISTANT,
        content=None,
        tool_calls=(tool_call,),
    )
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Echo: hello",
        tool_call_id="call_123",
    )
    assert provider.requests[1].tools == _snapshot(tool).model_tools


@pytest.mark.asyncio
async def test_loop_does_not_execute_tools_after_reaching_max_steps() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                ),
            ),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(provider, tool, max_steps=1).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.LIMIT_REACHED
    assert result.steps_used == 1
    assert tool.calls == 0


@pytest.mark.asyncio
async def test_loop_returns_an_error_result_for_unknown_tools() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="not_in_snapshot",
                        arguments={},
                    ),
                ),
            ),
            ModelResponse(text="I could not use that tool.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: requested tool is not in the run snapshot.",
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_returns_error_result_when_tool_execution_fails() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                ),
            ),
            ModelResponse(text="The tool failed.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool(RuntimeError("boom"))

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert tool.calls == 1
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool execution failed.",
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_appends_paired_tool_error_for_invalid_arguments() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": 1},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(text="I need text, not a number.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "I need text, not a number."
    assert tool.calls == 0
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool arguments are invalid.",
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_appends_paired_tool_error_for_missing_permission() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(
                text="I do not have permission for that tool.", tool_calls=()
            ),
        ),
    )
    tool = CountingEchoTool(
        required_permissions=frozenset({"tool.execute"}),
    )

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "I do not have permission for that tool."
    assert tool.calls == 0
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool permission denied.",
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_appends_paired_tool_error_when_execution_times_out() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(text="I could not complete the tool call.", tool_calls=()),
        ),
    )
    tool = HangingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "I could not complete the tool call."
    assert tool.calls == 1
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool execution timed out.",
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_blocks_the_third_call_with_equivalent_arguments() -> None:
    first_arguments = {"text": "hello", "attempt": 1}
    reordered_arguments = {"attempt": 1, "text": "hello"}
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_1",
                        name="builtin_echo",
                        arguments=first_arguments,
                    ),
                ),
            ),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_2",
                        name="builtin_echo",
                        arguments=reordered_arguments,
                    ),
                ),
            ),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_3",
                        name="builtin_echo",
                        arguments=first_arguments,
                    ),
                ),
            ),
            ModelResponse(text="I will stop retrying.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(
        provider,
        tool,
        max_steps=4,
        max_calls_per_tool_input=2,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.steps_used == 4
    assert tool.calls == 2
    assert provider.requests[3].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: repeated tool call limit reached.",
        tool_call_id="call_3",
    )


@pytest.mark.asyncio
async def test_loop_truncates_tool_result_before_returning_to_model() -> None:
    original_result = "x" * 100
    marker = "\n\n[Tool result truncated]"
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_123",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                ),
            ),
            ModelResponse(text="I received the shortened result.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool(result=original_result)

    await _loop(
        provider,
        tool,
        max_tool_result_chars=40,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    tool_message = provider.requests[1].messages[-1]
    assert tool_message.content == "x" * (40 - len(marker)) + marker
    assert len(tool_message.content) == 40
    assert tool.calls == 1


@pytest.mark.asyncio
async def test_loop_stops_before_model_when_cancelled() -> None:
    provider = FakeModelProvider()
    tool = CountingEchoTool()
    token = RunCancellationToken(RunId("run_123"))
    token.cancel()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        cancellation_token=token,
    )

    assert result.status is RunStatus.CANCELLED
    assert result.steps_used == 0
    assert result.messages == (_user_message(),)
    assert provider.requests == ()
    assert tool.calls == 0


@pytest.mark.asyncio
async def test_loop_fails_when_model_provider_times_out() -> None:
    provider = TimeoutModelProvider()
    tool = CountingEchoTool()

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.FAILED
    assert result.text is None
    assert result.error == "model call timed out"
    assert result.steps_used == 0
    assert result.messages == (_user_message(),)
    assert len(provider.requests) == 1
    assert tool.calls == 0


@pytest.mark.asyncio
async def test_loop_closes_pending_tool_calls_when_cancelled() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_1",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                    ModelToolCall(
                        call_id="call_2",
                        name="builtin_echo",
                        arguments={"text": "hello"},
                    ),
                ),
            ),
        ),
    )
    token = RunCancellationToken(RunId("run_123"))
    tool = CountingEchoTool(on_execute=token.cancel)

    result = await _loop(provider, tool).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        cancellation_token=token,
    )

    assert result.status is RunStatus.CANCELLED
    assert result.steps_used == 1
    assert tool.calls == 1
    assert result.messages[-2] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Echo: hello",
        tool_call_id="call_1",
    )
    assert result.messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool execution cancelled.",
        tool_call_id="call_2",
    )


def test_loop_requires_a_positive_step_limit() -> None:
    provider = FakeModelProvider()
    tool = CountingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ValueError, match="max_steps must be positive"):
        AgentLoop(
            model=provider,
            executor=ToolExecutor(registry),
            tool_snapshot=_snapshot(tool),
            max_steps=0,
        )

    with pytest.raises(
        ValueError,
        match="max_calls_per_tool_input must be positive",
    ):
        AgentLoop(
            model=provider,
            executor=ToolExecutor(registry),
            tool_snapshot=_snapshot(tool),
            max_calls_per_tool_input=0,
        )

    with pytest.raises(
        ValueError,
        match="max_tool_result_chars must fit the truncation marker",
    ):
        AgentLoop(
            model=provider,
            executor=ToolExecutor(registry),
            tool_snapshot=_snapshot(tool),
            max_tool_result_chars=1,
        )
