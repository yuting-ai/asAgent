import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.tools.mcp import McpClient, McpProtocolError, McpServerSession
from asagent.tools.registry import ToolRegistry

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_SERVER_PATH),
)
_EXITING_SERVER_COMMAND: Final = (
    sys.executable,
    "-c",
    "import sys; sys.stdin.readline()",
)


@pytest.mark.asyncio
async def test_session_starts_imports_tools_and_closes_its_client() -> None:
    client = McpClient(command=_SERVER_COMMAND)
    registry = ToolRegistry()
    session = McpServerSession(
        client=client,
        registry=registry,
        server_name="test-server",
    )

    try:
        server_info = await session.start()

        assert server_info.name == "asagent-test-server"
        assert len(registry.definitions()) == 1
        assert registry.definitions()[0].tool_id.startswith(
            "mcp:test-server:add:",
        )

        await session.aclose()

        with pytest.raises(RuntimeError, match="not started"):
            await client.list_tools()
        with pytest.raises(RuntimeError, match="session is closed"):
            await session.start()
    finally:
        await session.aclose()


@pytest.mark.asyncio
async def test_session_closes_client_when_startup_fails() -> None:
    client = McpClient(command=_EXITING_SERVER_COMMAND)
    session = McpServerSession(
        client=client,
        registry=ToolRegistry(),
        server_name="exiting-server",
    )

    try:
        with pytest.raises(McpProtocolError, match="closed stdout"):
            await session.start()

        with pytest.raises(RuntimeError, match="not started"):
            await client.list_tools()
        with pytest.raises(RuntimeError, match="session is closed"):
            await session.start()
    finally:
        await session.aclose()
