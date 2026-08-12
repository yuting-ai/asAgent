import asyncio
from collections.abc import Mapping

import pytest

from asagent.core.ids import ApprovalId, ConversationId, RunId
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.approval import (
    ToolApprovalRequest,
    ToolApprovalRequestedCallback,
)
from asagent.tools.errors import (
    ToolApprovalDeniedError,
    ToolArgumentsValidationError,
    ToolPermissionDeniedError,
    ToolTimeoutError,
)
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry


class RecordingTool:
    def __init__(
        self,
        required_permissions: frozenset[str] = frozenset(),
        requires_approval: bool = False,
    ) -> None:
        self.arguments: Mapping[str, object] | None = None
        self._required_permissions = required_permissions
        self._requires_approval = requires_approval

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
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
            required_permissions=self._required_permissions,
            requires_approval=self._requires_approval,
            timeout_seconds=1.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        self.arguments = arguments
        return f"Echo: {arguments['text']}"


class FailingTool(RecordingTool):
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.fail",
            display_name="Fail",
            description="Always fails.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        raise RuntimeError("tool failed")


class HangingTool(RecordingTool):
    def __init__(self) -> None:
        super().__init__()
        self.cancelled = False

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="builtin.hanging",
            display_name="Hanging",
            description="Never completes.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=0.01,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class RecordingApprovalPolicy:
    def __init__(self, approved: bool) -> None:
        self._approved = approved
        self.requests: list[tuple[ToolDefinition, Mapping[str, object]]] = []

    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        del on_requested
        self.requests.append((request.definition, request.arguments))
        return self._approved


def _approval_request(tool: RecordingTool) -> ToolApprovalRequest:
    return ToolApprovalRequest(
        approval_id=ApprovalId("approval-1"),
        run_id=RunId("run-1"),
        conversation_id=ConversationId("conversation-1"),
        tool_call_id="call-1",
        definition=tool.definition,
        arguments={"text": "hello"},
    )


@pytest.mark.asyncio
async def test_executor_delegates_to_registered_tool() -> None:
    tool = RecordingTool(frozenset({"tool.execute"}))
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(
        registry,
        granted_permissions=frozenset({"tool.execute"}),
    )

    result = await executor.execute("builtin.echo", {"text": "hello"})

    assert result == "Echo: hello"
    assert tool.arguments == {"text": "hello"}


@pytest.mark.asyncio
async def test_executor_rejects_unknown_tool_id() -> None:
    executor = ToolExecutor(ToolRegistry())

    with pytest.raises(KeyError, match="not registered"):
        await executor.execute("builtin.echo", {})


@pytest.mark.asyncio
async def test_executor_does_not_hide_tool_failure() -> None:
    registry = ToolRegistry()
    registry.register(FailingTool())
    executor = ToolExecutor(registry)

    with pytest.raises(RuntimeError, match="tool failed"):
        await executor.execute("builtin.fail", {})


@pytest.mark.asyncio
async def test_executor_rejects_invalid_arguments_before_execution() -> None:
    tool = RecordingTool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    with pytest.raises(
        ToolArgumentsValidationError,
        match="tool arguments are invalid",
    ):
        await executor.execute("builtin.echo", {"text": 1})

    assert tool.arguments is None


@pytest.mark.asyncio
async def test_executor_rejects_tools_without_required_permission() -> None:
    tool = RecordingTool(frozenset({"tool.execute"}))
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    with pytest.raises(
        ToolPermissionDeniedError,
        match="tool permission denied",
    ):
        await executor.execute("builtin.echo", {"text": "hello"})

    assert tool.arguments is None


@pytest.mark.asyncio
async def test_executor_executes_approved_tools() -> None:
    tool = RecordingTool(requires_approval=True)
    registry = ToolRegistry()
    registry.register(tool)
    policy = RecordingApprovalPolicy(True)
    executor = ToolExecutor(registry, approval_policy=policy)

    result = await executor.execute(
        "builtin.echo",
        {"text": "hello"},
        approval_request=_approval_request(tool),
    )

    assert result == "Echo: hello"
    assert tool.arguments == {"text": "hello"}
    assert policy.requests[0][0] == tool.definition


@pytest.mark.asyncio
async def test_executor_rejects_tools_without_approval_policy() -> None:
    tool = RecordingTool(requires_approval=True)
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    with pytest.raises(
        ToolApprovalDeniedError,
        match="tool approval denied",
    ):
        await executor.execute("builtin.echo", {"text": "hello"})

    assert tool.arguments is None


@pytest.mark.asyncio
async def test_executor_cancels_tool_when_execution_times_out() -> None:
    tool = HangingTool()
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(registry)

    with pytest.raises(ToolTimeoutError, match="tool execution timed out"):
        await executor.execute("builtin.hanging", {})

    assert tool.cancelled is True
