from collections.abc import Mapping

import pytest

from asagent.agent.loop import AgentLoop
from asagent.core.run_status import RunStatus
from asagent.core.tool_definition import ToolDefinition
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.fake_provider import FakeModelProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot


class CountingEchoTool:
    def __init__(
        self,
        error: Exception | None = None,
        result: str = "Echo: hello",
    ) -> None:
        self.calls = 0
        self._error = error
        self._result = result
        self._definition = ToolDefinition(
            tool_id="builtin.echo",
            display_name="Echo",
            description="Returns supplied text.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(self, arguments: Mapping[str, object]) -> str:
        self.calls += 1
        assert arguments["text"] == "hello"
        if self._error is not None:
            raise self._error
        return self._result


def _snapshot(tool: CountingEchoTool) -> ToolSnapshot:
    return ToolSnapshot.from_definitions(
        (tool.definition,),
        provider_name_for=openai_compatible_tool_name,
    )


def _loop(
    provider: FakeModelProvider,
    tool: CountingEchoTool,
    *,
    max_steps: int = 8,
    max_calls_per_tool_input: int | None = None,
    max_tool_result_chars: int = 4_000,
) -> AgentLoop:
    registry = ToolRegistry()
    registry.register(tool)

    return AgentLoop(
        model=provider,
        executor=ToolExecutor(registry),
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
