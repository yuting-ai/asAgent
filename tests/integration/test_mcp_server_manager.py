import os
import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.tools.mcp import McpProtocolError
from asagent.tools.mcp_config import McpServerConfigs
from asagent.tools.mcp_manager import McpServerManager
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


def _configs(
    *,
    working_directory: Path,
    servers: dict[str, tuple[str, ...]],
) -> McpServerConfigs:
    return McpServerConfigs.model_validate(
        {
            "servers": {
                name: {
                    "command": command,
                    "working_directory": str(working_directory),
                }
                for name, command in servers.items()
            }
        }
    )


@pytest.mark.asyncio
async def test_manager_imports_all_configured_servers_after_startup(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"test-server": _SERVER_COMMAND},
        ),
        registry=registry,
    )

    try:
        await manager.start()

        assert len(registry.definitions()) == 1
        assert registry.definitions()[0].tool_id.startswith(
            "mcp:test-server:add:",
        )
    finally:
        await manager.aclose()

    with pytest.raises(RuntimeError, match="manager is closed"):
        await manager.start()


@pytest.mark.asyncio
async def test_manager_passes_only_the_explicit_child_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASAGENT_TEST_MCP_PARENT_SECRET", "must-not-leak")
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"test-server": _SERVER_COMMAND},
        ),
        registry=registry,
        environment={"PATH": os.environ["PATH"]},
    )

    try:
        await manager.start()

        assert len(registry.definitions()) == 1
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_closes_started_sessions_without_importing_partial_tools(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "working-server": _SERVER_COMMAND,
                "exiting-server": _EXITING_SERVER_COMMAND,
            },
        ),
        registry=registry,
    )

    try:
        with pytest.raises(McpProtocolError, match="closed stdout"):
            await manager.start()

        assert registry.definitions() == ()
    finally:
        await manager.aclose()
