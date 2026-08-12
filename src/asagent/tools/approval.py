import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

from asagent.core.ids import ApprovalId, ConversationId, RunId
from asagent.core.tool_definition import ToolDefinition


class ToolApprovalDecision(StrEnum):
    DENY = "deny"
    ALLOW_ONCE = "allow_once"
    ALLOW_CONVERSATION = "allow_conversation"


@dataclass(frozen=True, slots=True)
class ToolApprovalRequest:
    approval_id: ApprovalId
    run_id: RunId
    conversation_id: ConversationId
    tool_call_id: str
    definition: ToolDefinition
    arguments: Mapping[str, object]


ToolApprovalRequestedCallback = Callable[[ToolApprovalRequest], Awaitable[None]]


class ToolApprovalPolicy(Protocol):
    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool: ...


@dataclass(slots=True)
class _PendingApproval:
    request: ToolApprovalRequest
    decision: asyncio.Future[bool]


class PendingToolApprovalPolicy:
    """Keeps one-time and conversation-scoped approvals in memory."""

    def __init__(self) -> None:
        self._pending: dict[ApprovalId, _PendingApproval] = {}
        self._conversation_grants: set[tuple[ConversationId, str]] = set()
        self._closed = False

    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        if self._closed or request.approval_id in self._pending:
            return False

        grant_key = _grant_key(request)
        if grant_key in self._conversation_grants:
            return True

        decision = asyncio.get_running_loop().create_future()
        pending = _PendingApproval(request=request, decision=decision)
        self._pending[request.approval_id] = pending

        try:
            if on_requested is not None:
                await on_requested(request)
            return cast(bool, await decision)
        except asyncio.CancelledError:
            if not decision.done():
                decision.set_result(False)
            raise
        finally:
            if self._pending.get(request.approval_id) is pending:
                self._pending.pop(request.approval_id)

    def get(self, approval_id: ApprovalId) -> ToolApprovalRequest | None:
        pending = self._pending.get(approval_id)
        return None if pending is None else pending.request

    def decide(
        self,
        approval_id: ApprovalId,
        decision: ToolApprovalDecision,
    ) -> bool:
        pending = self._pending.get(approval_id)
        if pending is None or pending.decision.done():
            return False

        if decision is ToolApprovalDecision.ALLOW_CONVERSATION:
            self._conversation_grants.add(_grant_key(pending.request))

        pending.decision.set_result(decision is not ToolApprovalDecision.DENY)
        return True

    def deny_run(self, run_id: RunId) -> None:
        for pending in tuple(self._pending.values()):
            if pending.request.run_id == run_id and not pending.decision.done():
                pending.decision.set_result(False)

    async def aclose(self) -> None:
        self._closed = True
        self._conversation_grants.clear()
        for pending in tuple(self._pending.values()):
            if not pending.decision.done():
                pending.decision.set_result(False)


def _grant_key(request: ToolApprovalRequest) -> tuple[ConversationId, str]:
    return (request.conversation_id, request.definition.tool_id)
