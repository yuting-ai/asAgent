import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.core.ids import ApprovalId, ConversationId, RunId
from asagent.tools.approval import ToolApprovalRequest, ToolApprovalRequestedCallback
from asagent.tools.executor import ToolExecutor
from asagent.tools.mcp import McpClient, register_mcp_tools
from asagent.tools.registry import ToolRegistry

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_SERVER_PATH),
)


class ApprovingPolicy:
    async def approve(
        self,
        request: ToolApprovalRequest,
        on_requested: ToolApprovalRequestedCallback | None = None,
    ) -> bool:
        del request, on_requested
        return True


@pytest.mark.asyncio
async def test_register_mcp_tools_exposes_add_through_executor() -> None:
    client = McpClient(command=_SERVER_COMMAND)
    registry = ToolRegistry()

    try:
        await client.start()
        await register_mcp_tools(
            registry,
            client,
            server_name="test-server",
        )

        add_tools = [
            definition
            for definition in registry.definitions()
            if definition.tool_id.startswith("mcp:test-server:add:")
        ]
        assert len(add_tools) == 1
        add_tool = add_tools[0]

        assert add_tool.risk_level == "medium"
        assert add_tool.required_permissions == frozenset({"mcp.execute"})
        assert add_tool.requires_approval is True
        assert add_tool.display_name == "Add numbers"
        assert add_tool.description == "Add two numbers."

        executor = ToolExecutor(
            registry,
            granted_permissions=frozenset({"mcp.execute"}),
            approval_policy=ApprovingPolicy(),
        )

        result = await executor.execute(
            add_tool.tool_id,
            {"left": 2, "right": 3},
            approval_request=ToolApprovalRequest(
                approval_id=ApprovalId("approval-1"),
                run_id=RunId("run-1"),
                conversation_id=ConversationId("conversation-1"),
                tool_call_id="call-1",
                definition=add_tool,
                arguments={"left": 2, "right": 3},
            ),
        )

        assert result == "5"
    finally:
        await client.aclose()
