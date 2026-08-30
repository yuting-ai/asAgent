import asyncio
import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.tools.mcp import McpClient, McpProtocolError, McpServerSession

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_SERVER_PATH),
)
_SUBSCRIBE_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
)
_EXITING_SERVER_COMMAND: Final = (
    sys.executable,
    "-c",
    "import sys; sys.stdin.readline()",
)


@pytest.mark.asyncio
async def test_session_starts_imports_tools_and_closes_its_client() -> None:
    client = McpClient(command=_SERVER_COMMAND)
    session = McpServerSession(
        client=client,
        server_name="test-server",
    )

    try:
        server_info = await session.start()

        assert server_info.name == "asagent-test-server"
        assert len(session.registry.definitions()) == 1
        assert session.registry.definitions()[0].tool_id.startswith(
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


@pytest.mark.asyncio
async def test_session_automatically_subscribes_and_updates_private_registry() -> None:
    client = McpClient(command=_SUBSCRIBE_SERVER_COMMAND)
    update_event = asyncio.Event()

    async def _on_updated() -> None:
        update_event.set()

    session = McpServerSession(
        client=client,
        server_name="sub-server",
        on_registry_updated=_on_updated,
    )

    try:
        server_info = await session.start()
        assert server_info.supports_tool_list_changed is True

        await asyncio.wait_for(update_event.wait(), timeout=2.0)

        tool_ids = tuple(d.tool_id for d in session.registry.definitions())
        assert len(tool_ids) == 2
        assert any("add" in tid for tid in tool_ids)
        assert any("multiply" in tid for tid in tool_ids)
    finally:
        await session.aclose()
