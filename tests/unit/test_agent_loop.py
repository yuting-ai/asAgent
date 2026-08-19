import asyncio
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime

import pytest

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.context_budget import (
    ConservativeUtf8TokenEstimator,
    ContextBudget,
    ModelContextCapabilities,
)
from asagent.agent.context_builder import ContextBuilder
from asagent.agent.loop import AgentLoop
from asagent.core.event_publisher import EventPublisher
from asagent.core.ids import ConversationId, EventId, RunId, ToolCallId
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall
from asagent.core.tool_call_recorder import ToolCallRecorder
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
from asagent.tools.approval import (
    ToolApprovalPolicy,
    ToolApprovalRequest,
    ToolApprovalRequestedCallback,
)
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
        requires_approval: bool = False,
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
            requires_approval=requires_approval,
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


class OperationErrorTool(CountingEchoTool):
    async def execute(self, arguments: Mapping[str, object]) -> str:
        from asagent.tools.errors import ToolOperationError

        self.calls += 1
        del arguments
        raise ToolOperationError("target is obscured")


class FixedApprovalPolicy:
    def __init__(self, approved: bool) -> None:
        self._approved = approved

    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        del request, on_requested
        return self._approved


class CollectingEventPublisher:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []

    async def publish(self, event: RunEvent) -> None:
        self.events.append(event)


class FailingEventPublisher:
    def __init__(self, event_type: str) -> None:
        self.events: list[RunEvent] = []
        self._event_type = event_type

    async def publish(self, event: RunEvent) -> None:
        self.events.append(event)
        if event.event_type == self._event_type:
            raise RuntimeError("event publisher failed")


class CollectingToolCallRecorder:
    def __init__(self) -> None:
        self.recorded: list[ToolCall] = []

    async def record(self, tool_call: ToolCall) -> None:
        self.recorded.append(tool_call)


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
    approval_policy: ToolApprovalPolicy | None = None,
    event_publisher: EventPublisher | None = None,
    event_id_factory: Callable[[], EventId] | None = None,
    clock: Callable[[], datetime] | None = None,
    tool_call_recorder: ToolCallRecorder | None = None,
    tool_call_id_factory: Callable[[], ToolCallId] | None = None,
    context_builder: ContextBuilder | None = None,
) -> AgentLoop:
    registry = ToolRegistry()
    registry.register(tool)

    return AgentLoop(
        model=provider,
        executor=ToolExecutor(
            registry,
            granted_permissions=granted_permissions,
            approval_policy=approval_policy,
        ),
        tool_snapshot=_snapshot(tool),
        max_steps=max_steps,
        max_calls_per_tool_input=max_calls_per_tool_input,
        max_tool_result_chars=max_tool_result_chars,
        event_publisher=event_publisher,
        event_id_factory=event_id_factory,
        clock=clock,
        tool_call_recorder=tool_call_recorder,
        tool_call_id_factory=tool_call_id_factory,
        context_builder=context_builder,
    )


def _user_message() -> ModelMessage:
    return ModelMessage(
        role=ModelMessageRole.USER,
        content="Please echo hello.",
    )


def _context_builder(input_budget_tokens: int) -> ContextBuilder:
    return ContextBuilder(
        budget=ContextBudget(
            max_input_tokens=input_budget_tokens,
            reserved_output_tokens=1,
        ).resolve(
            ModelContextCapabilities(
                context_window_tokens=input_budget_tokens + 1,
            ),
        ),
        estimator=ConservativeUtf8TokenEstimator(),
    )


def _message_tokens(messages: tuple[ModelMessage, ...]) -> int:
    estimator = ConservativeUtf8TokenEstimator()
    return sum(estimator.estimate_message(message) for message in messages)


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
async def test_loop_appends_paired_tool_error_for_rejected_approval() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(text="I will not run that without approval.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool(requires_approval=True)

    result = await _loop(
        provider,
        tool,
        approval_policy=FixedApprovalPolicy(False),
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.text == "I will not run that without approval."
    assert tool.calls == 0
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: tool approval denied.",
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
        content=(
            "Error: tool execution timed out. "
            "Do not retry the same tool call with the same arguments."
        ),
        tool_call_id="call_123",
    )


@pytest.mark.asyncio
async def test_loop_blocks_the_second_identical_call_when_limit_is_one() -> None:
    tool_call = ModelToolCall(
        call_id="call_1",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_2",
                        name="builtin_echo",
                        arguments={"text": "hello"},
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
        max_calls_per_tool_input=1,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.steps_used == 3
    assert tool.calls == 1
    assert provider.requests[2].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: repeated tool call limit reached.",
        tool_call_id="call_2",
    )


@pytest.mark.asyncio
async def test_loop_returns_allowlisted_tool_operation_errors() -> None:
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
                ),
            ),
            ModelResponse(text="The target was obscured.", tool_calls=()),
        ),
    )
    tool = OperationErrorTool()

    result = await _loop(provider, tool, max_steps=3).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert tool.calls == 1
    assert provider.requests[1].messages[-1] == ModelMessage(
        role=ModelMessageRole.TOOL,
        content="Error: target is obscured",
        tool_call_id="call_1",
    )


@pytest.mark.asyncio
async def test_loop_allows_identical_call_after_a_different_tool_input() -> None:
    provider = FakeModelProvider(
        responses=(
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_1",
                        name="builtin_echo",
                        arguments={"text": "page"},
                    ),
                ),
            ),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_2",
                        name="builtin_echo",
                        arguments={"text": "click"},
                    ),
                ),
            ),
            ModelResponse(
                text=None,
                tool_calls=(
                    ModelToolCall(
                        call_id="call_3",
                        name="builtin_echo",
                        arguments={"text": "page"},
                    ),
                ),
            ),
            ModelResponse(text="Read the page again after the click.", tool_calls=()),
        ),
    )
    tool = CountingEchoTool()

    result = await _loop(
        provider,
        tool,
        max_steps=4,
        max_calls_per_tool_input=1,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.COMPLETED
    assert result.steps_used == 4
    assert tool.calls == 3


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


@pytest.mark.asyncio
async def test_loop_publishes_ordered_safe_events_for_a_tool_round() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text=None, tool_calls=(tool_call,)),
            ModelResponse(text="The tool replied.", tool_calls=()),
        ),
    )
    publisher = CollectingEventPublisher()
    event_ids = iter(EventId(f"evt_{index}") for index in range(1, 9))
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

    result = await _loop(
        provider,
        CountingEchoTool(),
        event_publisher=publisher,
        event_id_factory=lambda: next(event_ids),
        clock=lambda: now,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
    )

    assert result.status is RunStatus.COMPLETED
    assert [event.event_type for event in publisher.events] == [
        "run.started",
        "model.requested",
        "model.completed",
        "tool.requested",
        "tool.completed",
        "model.requested",
        "model.completed",
        "run.completed",
    ]
    assert [event.sequence for event in publisher.events] == list(range(1, 9))
    assert [event.event_id for event in publisher.events] == [
        f"evt_{index}" for index in range(1, 9)
    ]
    assert all(event.run_id == "run_123" for event in publisher.events)
    assert all(event.conversation_id == "conv_123" for event in publisher.events)
    assert publisher.events[3].data == {
        "tool_call_id": "call_123",
        "provider_tool_name": "builtin_echo",
        "tool_id": "builtin.echo",
        "display_name": "Echo",
    }
    assert publisher.events[4].data == {
        "tool_call_id": "call_123",
        "tool_id": "builtin.echo",
        "display_name": "Echo",
    }
    assert all("hello" not in str(event.data) for event in publisher.events)


@pytest.mark.asyncio
async def test_loop_publishes_failed_terminal_event_for_model_timeout() -> None:
    publisher = CollectingEventPublisher()
    event_ids = iter(EventId(f"evt_{index}") for index in range(1, 4))
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)

    result = await _loop(
        TimeoutModelProvider(),
        CountingEchoTool(),
        event_publisher=publisher,
        event_id_factory=lambda: next(event_ids),
        clock=lambda: now,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
    )

    assert result.status is RunStatus.FAILED
    assert [event.event_type for event in publisher.events] == [
        "run.started",
        "model.requested",
        "run.failed",
    ]
    assert publisher.events[-1].data == {"steps_used": 0}


@pytest.mark.asyncio
async def test_loop_publishes_cancelled_and_limit_reached_terminal_events() -> None:
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    cancelled_publisher = CollectingEventPublisher()
    token = RunCancellationToken(RunId("run_123"))
    token.cancel()

    cancelled = await _loop(
        FakeModelProvider(),
        CountingEchoTool(),
        event_publisher=cancelled_publisher,
        event_id_factory=lambda: EventId("evt_cancelled"),
        clock=lambda: now,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        cancellation_token=token,
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
    )
    limit_publisher = CollectingEventPublisher()

    limit_reached = await _loop(
        FakeModelProvider(
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
        ),
        CountingEchoTool(),
        max_steps=1,
        event_publisher=limit_publisher,
        event_id_factory=lambda: EventId("evt_limit"),
        clock=lambda: now,
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
    )

    assert cancelled.status is RunStatus.CANCELLED
    assert [event.event_type for event in cancelled_publisher.events] == [
        "run.started",
        "run.cancelled",
    ]
    assert limit_reached.status is RunStatus.LIMIT_REACHED
    assert [event.event_type for event in limit_publisher.events] == [
        "run.started",
        "model.requested",
        "model.completed",
        "run.limit_reached",
    ]


@pytest.mark.asyncio
async def test_loop_stops_when_event_publishing_fails() -> None:
    tool_call = ModelToolCall(
        call_id="call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    publisher = FailingEventPublisher("model.completed")
    tool = CountingEchoTool()

    result = await _loop(
        FakeModelProvider(
            responses=(ModelResponse(text=None, tool_calls=(tool_call,)),),
        ),
        tool,
        event_publisher=publisher,
        event_id_factory=lambda: EventId("evt_123"),
        clock=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        run_id=RunId("run_123"),
        conversation_id=ConversationId("conv_123"),
    )

    assert result.status is RunStatus.FAILED
    assert result.error == "run event publishing failed"
    assert tool.calls == 0
    assert [event.event_type for event in publisher.events] == [
        "run.started",
        "model.requested",
        "model.completed",
    ]


@pytest.mark.asyncio
async def test_loop_records_raw_tool_results_with_an_internal_identity() -> None:
    tool_call = ModelToolCall(
        call_id="provider_call_123",
        name="builtin_echo",
        arguments={"text": "hello"},
    )
    recorder = CollectingToolCallRecorder()
    result = await _loop(
        FakeModelProvider(
            responses=(
                ModelResponse(text=None, tool_calls=(tool_call,)),
                ModelResponse(text="Done.", tool_calls=()),
            ),
        ),
        CountingEchoTool(result="x" * 100),
        max_tool_result_chars=40,
        tool_call_recorder=recorder,
        tool_call_id_factory=lambda: ToolCallId("tool_123"),
        clock=lambda: datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
        run_id=RunId("run_123"),
    )

    assert result.status is RunStatus.COMPLETED
    assert recorder.recorded == [
        ToolCall(
            tool_call_id=ToolCallId("tool_123"),
            run_id=RunId("run_123"),
            model_call_id="provider_call_123",
            tool_id="builtin.echo",
            arguments={"text": "hello"},
            result="x" * 100,
            error=None,
            created_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
            completed_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
        ),
    ]


def test_loop_requires_a_positive_step_limit() -> None:
    provider = FakeModelProvider()
    tool = CountingEchoTool()
    registry = ToolRegistry()
    registry.register(tool)

    with pytest.raises(ValueError, match="max_steps must be between 1 and 50"):
        AgentLoop(
            model=provider,
            executor=ToolExecutor(registry),
            tool_snapshot=_snapshot(tool),
            max_steps=0,
        )

    with pytest.raises(ValueError, match="max_steps must be between 1 and 50"):
        AgentLoop(
            model=provider,
            executor=ToolExecutor(registry),
            tool_snapshot=_snapshot(tool),
            max_steps=51,
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


@pytest.mark.asyncio
async def test_loop_uses_context_snapshot_request_when_builder_is_configured() -> None:
    provider = FakeModelProvider(
        responses=(ModelResponse(text="Hello!", tool_calls=()),),
    )
    tool = CountingEchoTool()
    old_history = (
        ModelMessage(role=ModelMessageRole.USER, content="old question"),
        ModelMessage(role=ModelMessageRole.ASSISTANT, content="old answer"),
    )
    current_message = _user_message()
    estimator = ConservativeUtf8TokenEstimator()
    system_prompt = "Be helpful."
    fixed_tokens = estimator.estimate_system_prompt(system_prompt) + sum(
        estimator.estimate_tool_definition(tool_definition)
        for tool_definition in _snapshot(tool).model_tools
    )

    result = await _loop(
        provider,
        tool,
        context_builder=_context_builder(
            fixed_tokens + _message_tokens((current_message,)),
        ),
    ).run(
        model_name="fake-model",
        system_prompt=system_prompt,
        messages=old_history + (current_message,),
    )

    assert result.status is RunStatus.COMPLETED
    assert provider.requests[0].messages == (current_message,)
    assert provider.requests[0].tools == _snapshot(tool).model_tools


@pytest.mark.asyncio
async def test_loop_fails_without_calling_the_model_when_context_exceeds_budget() -> (
    None
):
    provider = FakeModelProvider()
    tool = CountingEchoTool()

    result = await _loop(
        provider,
        tool,
        context_builder=_context_builder(1),
    ).run(
        model_name="fake-model",
        system_prompt="Be helpful.",
        messages=(_user_message(),),
    )

    assert result.status is RunStatus.FAILED
    assert result.error == "context budget exceeded"
    assert result.steps_used == 0
    assert result.messages == (_user_message(),)
    assert provider.requests == ()
