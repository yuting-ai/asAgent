import asyncio

import pytest

from asagent.core.ids import ApprovalId, ConversationId, RunId
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.approval import (
    PendingToolApprovalPolicy,
    ToolApprovalDecision,
    ToolApprovalRequest,
)


def _request(
    *,
    approval_id: str = "approval-1",
    conversation_id: str = "conversation-1",
    tool_id: str = "mcp:test-server:add:1234",
) -> ToolApprovalRequest:
    return ToolApprovalRequest(
        approval_id=ApprovalId(approval_id),
        run_id=RunId("run-1"),
        conversation_id=ConversationId(conversation_id),
        tool_call_id="call-1",
        definition=ToolDefinition(
            tool_id=tool_id,
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
    assert policy.decide(request.approval_id, ToolApprovalDecision.ALLOW_ONCE) is True
    assert await waiting is True
    assert policy.get(request.approval_id) is None


@pytest.mark.asyncio
async def test_allow_once_still_prompts_for_the_same_tool() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    second = _request(approval_id="approval-2")
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(first, on_requested))
    await asyncio.sleep(0)
    assert policy.decide(first.approval_id, ToolApprovalDecision.ALLOW_ONCE) is True
    assert await waiting is True

    waiting_again = asyncio.create_task(policy.approve(second, on_requested))
    await asyncio.sleep(0)

    assert observed == ["approval-1", "approval-2"]
    assert policy.decide(second.approval_id, ToolApprovalDecision.DENY) is True
    assert await waiting_again is False


@pytest.mark.asyncio
async def test_allow_conversation_rejected_when_definition_disallows_it() -> None:
    policy = PendingToolApprovalPolicy()
    request = ToolApprovalRequest(
        approval_id=ApprovalId("approval-1"),
        run_id=RunId("run-1"),
        conversation_id=ConversationId("conversation-1"),
        tool_call_id="call-1",
        definition=ToolDefinition(
            tool_id="browser.submit",
            display_name="Submit form",
            description="Submit once.",
            input_schema={"type": "object"},
            risk_level="high",
            required_permissions=frozenset({"browser.submit"}),
            requires_approval=True,
            timeout_seconds=10.0,
            allows_conversation_approval=False,
        ),
        arguments={"selector": "form#checkout"},
    )

    waiting = asyncio.create_task(policy.approve(request))
    await asyncio.sleep(0)

    assert (
        policy.decide(request.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is False
    )
    assert policy.decide(request.approval_id, ToolApprovalDecision.ALLOW_ONCE) is True
    assert await waiting is True


@pytest.mark.asyncio
async def test_allow_conversation_skips_later_prompts_for_the_same_tool() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    second = _request(approval_id="approval-2")
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(first, on_requested))
    await asyncio.sleep(0)
    assert (
        policy.decide(first.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is True
    )
    assert await waiting is True
    assert await policy.approve(second, on_requested) is True
    assert observed == ["approval-1"]


@pytest.mark.asyncio
async def test_conversation_grant_does_not_apply_to_another_conversation() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    other_conversation = _request(
        approval_id="approval-2",
        conversation_id="conversation-2",
    )
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(first, on_requested))
    await asyncio.sleep(0)
    assert (
        policy.decide(first.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is True
    )
    assert await waiting is True

    waiting_again = asyncio.create_task(
        policy.approve(other_conversation, on_requested),
    )
    await asyncio.sleep(0)

    assert observed == ["approval-1", "approval-2"]
    assert (
        policy.decide(
            other_conversation.approval_id,
            ToolApprovalDecision.DENY,
        )
        is True
    )
    assert await waiting_again is False


@pytest.mark.asyncio
async def test_conversation_grant_does_not_apply_to_another_tool() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    other_tool = _request(
        approval_id="approval-2",
        tool_id="mcp:gmail:send_email:abcd",
    )
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(first, on_requested))
    await asyncio.sleep(0)
    assert (
        policy.decide(first.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is True
    )
    assert await waiting is True

    waiting_again = asyncio.create_task(policy.approve(other_tool, on_requested))
    await asyncio.sleep(0)

    assert observed == ["approval-1", "approval-2"]
    assert policy.decide(other_tool.approval_id, ToolApprovalDecision.DENY) is True
    assert await waiting_again is False


@pytest.mark.asyncio
async def test_file_change_grant_applies_to_every_single_file_write_tool() -> None:
    policy = PendingToolApprovalPolicy()
    create = _request(
        approval_id="approval-create",
        tool_id="filesystem.create_file",
    )
    replace = _request(
        approval_id="approval-replace",
        tool_id="filesystem.replace_file",
    )
    delete = _request(
        approval_id="approval-delete",
        tool_id="filesystem.delete_file",
    )
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(create, on_requested))
    await asyncio.sleep(0)
    assert (
        policy.decide(create.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is True
    )
    assert await waiting is True

    assert await policy.approve(replace, on_requested) is True
    assert await policy.approve(delete, on_requested) is True
    assert observed == ["approval-create"]


@pytest.mark.asyncio
async def test_deny_does_not_create_a_conversation_grant() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    second = _request(approval_id="approval-2")
    observed: list[str] = []

    async def on_requested(item: ToolApprovalRequest) -> None:
        observed.append(str(item.approval_id))

    waiting = asyncio.create_task(policy.approve(first, on_requested))
    await asyncio.sleep(0)
    assert policy.decide(first.approval_id, ToolApprovalDecision.DENY) is True
    assert await waiting is False

    waiting_again = asyncio.create_task(policy.approve(second, on_requested))
    await asyncio.sleep(0)

    assert observed == ["approval-1", "approval-2"]
    assert policy.decide(second.approval_id, ToolApprovalDecision.DENY) is True
    assert await waiting_again is False


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


@pytest.mark.asyncio
async def test_aclose_clears_conversation_grants() -> None:
    policy = PendingToolApprovalPolicy()
    first = _request(approval_id="approval-1")
    second = _request(approval_id="approval-2")

    waiting = asyncio.create_task(policy.approve(first))
    await asyncio.sleep(0)
    assert (
        policy.decide(first.approval_id, ToolApprovalDecision.ALLOW_CONVERSATION)
        is True
    )
    assert await waiting is True

    await policy.aclose()

    assert policy._conversation_grants == set()
    assert await policy.approve(second) is False
