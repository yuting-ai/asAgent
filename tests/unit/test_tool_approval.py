import asyncio

import pytest

from asagent.core.ids import ApprovalId, ConversationId, RunId
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.approval import PendingToolApprovalPolicy, ToolApprovalRequest


def _request() -> ToolApprovalRequest:
    return ToolApprovalRequest(
        approval_id=ApprovalId("approval-1"),
        run_id=RunId("run-1"),
        conversation_id=ConversationId("conversation-1"),
        tool_call_id="call-1",
        definition=ToolDefinition(
            tool_id="mcp:test-server:add:1234",
            display_name="Add numbers",
            description="Add two numbers.",
            input_schema={"type": "object"},
            risk_level="medium",
            required_permissions=frozenset({"mcp.execute"}),
            requires_approval=True,
            timeout_seconds=10.0,
        ),
        arguments={"left": 2, "right": 3},
    )


@pytest.mark.asyncio
async def test_pending_approval_publishes_only_after_storing_request() -> None:
    policy = PendingToolApprovalPolicy()
    request = _request()
    observed: list[ToolApprovalRequest] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(item)
        assert policy.get(item.approval_id) == item

    waiting = asyncio.create_task(policy.approve(request, on_requested))
    await asyncio.sleep(0)

    assert observed == [request]
    assert policy.decide(request.approval_id, True) is True
    assert await waiting is True
    assert policy.get(request.approval_id) is None


@pytest.mark.asyncio
async def test_pending_approval_denies_when_run_is_cancelled_or_policy_closes() -> None:
    policy = PendingToolApprovalPolicy()
    request = _request()

    waiting = asyncio.create_task(policy.approve(request))
    await asyncio.sleep(0)
    policy.deny_run(request.run_id)

    assert await waiting is False

    await policy.aclose()
    assert await policy.approve(request) is False
