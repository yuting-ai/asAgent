import asyncio
from collections.abc import Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from asagent.core.tool import Tool
from asagent.tools.approval import (
    ToolApprovalPolicy,
    ToolApprovalRequest,
    ToolApprovalRequestedCallback,
)
from asagent.tools.errors import (
    ToolApprovalDeniedError,
    ToolArgumentsValidationError,
    ToolPermissionDeniedError,
    ToolTimeoutError,
)
from asagent.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        granted_permissions: frozenset[str] = frozenset(),
        approval_policy: ToolApprovalPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._granted_permissions = granted_permissions
        self._approval_policy = approval_policy

    async def execute(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
        *,
        approval_request: ToolApprovalRequest | None = None,
        on_approval_requested: ToolApprovalRequestedCallback | None = None,
    ) -> str:
        tool: Tool = self._registry.get(tool_id)

        try:
            Draft202012Validator(tool.definition.input_schema).validate(
                dict(arguments),
            )
        except ValidationError as error:
            raise ToolArgumentsValidationError(
                "tool arguments are invalid",
            ) from error

        if not tool.definition.required_permissions.issubset(
            self._granted_permissions,
        ):
            raise ToolPermissionDeniedError("tool permission denied")

        if tool.definition.requires_approval and (
            self._approval_policy is None or approval_request is None
        ):
            raise ToolApprovalDeniedError("tool approval denied")

        if tool.definition.requires_approval:
            assert self._approval_policy is not None
            assert approval_request is not None
            if not await self._approval_policy.approve(
                approval_request,
                on_approval_requested,
            ):
                raise ToolApprovalDeniedError("tool approval denied")

        try:
            return await asyncio.wait_for(
                tool.execute(arguments),
                timeout=tool.definition.timeout_seconds,
            )
        except TimeoutError as error:
            raise ToolTimeoutError("tool execution timed out") from error
