import os
import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.core.connection import CredentialStore
from asagent.core.ids import ConnectionId
from asagent.tools.mcp import McpProtocolError
from asagent.tools.mcp_config import McpServerConfigs
from asagent.tools.mcp_manager import McpServerCredentialError, McpServerManager
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
_TEST_CREDENTIAL_ENVIRONMENT: Final = "ASAGENT_TEST_MCP_CREDENTIAL"
_TEST_CREDENTIAL: Final = "test-connection-credential"


class FakeCredentialStore:
    def __init__(self, credentials: dict[ConnectionId, str]) -> None:
        self._credentials = credentials
        self.requested_connection_ids: list[ConnectionId] = []

    def get_credential(self, connection_id: ConnectionId) -> str | None:
        self.requested_connection_ids.append(connection_id)
        return self._credentials.get(connection_id)

    def save_credential(
        self,
        connection_id: ConnectionId,
        credential: str,
    ) -> None:
        raise AssertionError("not used by MCP server startup")

    def delete_credential(self, connection_id: ConnectionId) -> None:
        raise AssertionError("not used by MCP server startup")


def _configs(
    *,
    working_directory: Path,
    servers: dict[str, tuple[str, ...]],
    credential_references: dict[str, dict[str, object]] | None = None,
) -> McpServerConfigs:
    references = credential_references or {}
    return McpServerConfigs.model_validate(
        {
            "servers": {
                name: {
                    "command": command,
                    "working_directory": str(working_directory),
                    **references.get(name, {}),
                }
                for name, command in servers.items()
            }
        }
    )


_MULTI_TOOL_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--expose-multiply",
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


@pytest.mark.asyncio
async def test_manager_injects_a_connection_credential_only_into_its_server(
    tmp_path: Path,
) -> None:
    connection_id = ConnectionId("connection-1")
    store: CredentialStore = FakeCredentialStore(
        {connection_id: _TEST_CREDENTIAL},
    )
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "credential-server": (
                    *_SERVER_COMMAND,
                    "--require-credential",
                ),
                "plain-server": (
                    *_SERVER_COMMAND,
                    "--reject-credential",
                ),
            },
            credential_references={
                "credential-server": {
                    "connection_id": str(connection_id),
                    "credential_environment_variable": (_TEST_CREDENTIAL_ENVIRONMENT),
                }
            },
        ),
        registry=registry,
        environment={"PATH": os.environ["PATH"]},
        credential_store=store,
    )

    try:
        await manager.start()

        assert len(registry.definitions()) == 2
        assert isinstance(store, FakeCredentialStore)
        assert store.requested_connection_ids == [connection_id]
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_imports_only_allowed_tools(tmp_path: Path) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"test-server": _MULTI_TOOL_SERVER_COMMAND},
            credential_references={
                "test-server": {
                    "allowed_tools": ["add"],
                }
            },
        ),
        registry=registry,
    )

    try:
        await manager.start()

        tool_ids = {definition.tool_id for definition in registry.definitions()}
        assert len(tool_ids) == 1
        assert next(iter(tool_ids)).startswith("mcp:test-server:add:")
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_imports_all_tools_when_allowed_tools_is_omitted(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"test-server": _MULTI_TOOL_SERVER_COMMAND},
        ),
        registry=registry,
    )

    try:
        await manager.start()

        tool_ids = {definition.tool_id for definition in registry.definitions()}
        assert len(tool_ids) == 2
        assert any(tool_id.startswith("mcp:test-server:add:") for tool_id in tool_ids)
        assert any(
            tool_id.startswith("mcp:test-server:multiply:") for tool_id in tool_ids
        )
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_rejects_missing_allowed_tool_without_registry_pollution(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"test-server": _MULTI_TOOL_SERVER_COMMAND},
            credential_references={
                "test-server": {
                    "allowed_tools": ["add", "missing-tool"],
                }
            },
        ),
        registry=registry,
    )

    try:
        with pytest.raises(
            ValueError,
            match="MCP allowed tool is not exposed by server .test-server.: .missing-tool.",
        ):
            await manager.start()

        assert registry.definitions() == ()
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_rejects_missing_configured_connection_credential(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={"credential-server": _SERVER_COMMAND},
            credential_references={
                "credential-server": {
                    "connection_id": "connection-missing",
                    "credential_environment_variable": (_TEST_CREDENTIAL_ENVIRONMENT),
                }
            },
        ),
        registry=registry,
        credential_store=FakeCredentialStore({}),
    )

    try:
        with pytest.raises(
            McpServerCredentialError,
            match="credential is unavailable",
        ):
            await manager.start()

        assert registry.definitions() == ()
    finally:
        await manager.aclose()
