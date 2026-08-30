import asyncio
import os
import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.core.connection import CredentialStore
from asagent.core.ids import ConnectionId
from asagent.core.tool import Tool
from asagent.core.tool_definition import ToolDefinition
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
        await manager.start()

        assert manager.has_active_servers
        assert "exiting-server" in manager.failed_servers
        assert "working-server" not in manager.failed_servers
        assert len(registry.definitions()) == 1
        assert registry.definitions()[0].tool_id.startswith(
            "mcp:working-server:add:",
        )
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
        await manager.start()

        assert not manager.has_active_servers
        assert "test-server" in manager.failed_servers
        assert "missing-tool" in manager.failed_servers["test-server"]
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
        await manager.start()

        assert not manager.has_active_servers
        assert "credential-server" in manager.failed_servers
        assert (
            "credential is unavailable" in manager.failed_servers["credential-server"]
        )
        assert registry.definitions() == ()
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_isolates_failed_server_and_imports_healthy_server(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "healthy-server": _SERVER_COMMAND,
                "bad-server": ("non_existent_binary_xyz_12345",),
            },
        ),
        registry=registry,
    )

    try:
        await manager.start()

        assert manager.has_active_servers
        assert manager.active_server_count == 1
        assert "bad-server" in manager.failed_servers
        assert "healthy-server" not in manager.failed_servers
        assert len(registry.definitions()) == 1
        assert registry.definitions()[0].tool_id.startswith(
            "mcp:healthy-server:add:",
        )
    finally:
        await manager.aclose()


class _StubBuiltinTool:
    def __init__(self, tool_id: str) -> None:
        self._definition = ToolDefinition(
            tool_id=tool_id,
            display_name=tool_id,
            description="Builtin stub tool.",
            input_schema={"type": "object"},
            risk_level="low",
            required_permissions=frozenset(),
            requires_approval=False,
            timeout_seconds=1.0,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(self, arguments: object) -> str:
        return "builtin-stub"


@pytest.mark.asyncio
async def test_manager_atomic_recomposition_and_dynamic_refresh(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    builtin_tool: Tool = _StubBuiltinTool("builtin.echo")
    registry.register(builtin_tool)

    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "static-server": _SERVER_COMMAND,
                "dynamic-server": (
                    *_SERVER_COMMAND,
                    "--emit-tool-list-change",
                ),
            },
        ),
        registry=registry,
    )

    try:
        # Pre-capture run snapshot before dynamic refresh propagates
        await manager.start()

        # Immediately after startup, wait briefly or poll for the dynamic update
        # Give enough time for notification + list_tools to recompose
        for _ in range(50):
            tool_ids = {d.tool_id for d in registry.definitions()}
            if any("dynamic-server:multiply" in tid for tid in tool_ids):
                break
            await asyncio.sleep(0.05)

        tool_ids = {d.tool_id for d in registry.definitions()}
        assert "builtin.echo" in tool_ids
        assert any("static-server:add:" in tid for tid in tool_ids)
        assert any("dynamic-server:add:" in tid for tid in tool_ids)
        assert any("dynamic-server:multiply:" in tid for tid in tool_ids)

        # Snapshot of new Run
        new_run_snapshot = registry.copy()
        new_run_tool_ids = {d.tool_id for d in new_run_snapshot.definitions()}
        assert new_run_tool_ids == tool_ids
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_preserves_previous_run_snapshots_during_and_after_refresh(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    builtin_tool: Tool = _StubBuiltinTool("builtin.calculator")
    registry.register(builtin_tool)

    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "static-server": _SERVER_COMMAND,
                "dynamic-server": (
                    *_SERVER_COMMAND,
                    "--emit-tool-list-change",
                ),
            },
        ),
        registry=registry,
    )

    try:
        await manager.start()

        # Run 1 snapshot contains initial MCP tool "add"
        run1_registry = registry.copy()
        run1_tool_ids = {d.tool_id for d in run1_registry.definitions()}
        assert "builtin.calculator" in run1_tool_ids
        assert any("static-server:add:" in tid for tid in run1_tool_ids)
        assert any("dynamic-server:add:" in tid for tid in run1_tool_ids)
        assert not any("dynamic-server:multiply:" in tid for tid in run1_tool_ids)

        # Wait for dynamic refresh to propagate
        for _ in range(50):
            tool_ids = {d.tool_id for d in registry.definitions()}
            if any("dynamic-server:multiply" in tid for tid in tool_ids):
                break
            await asyncio.sleep(0.05)

        # Verify run1_registry was NEVER mutated by the refresh and still only has "add"
        run1_tool_ids_after_refresh = {d.tool_id for d in run1_registry.definitions()}
        assert run1_tool_ids_after_refresh == run1_tool_ids
        assert not any(
            "dynamic-server:multiply:" in tid for tid in run1_tool_ids_after_refresh
        )

        # Verify a new Run snapshot created after refresh sees "multiply"
        run2_registry = registry.copy()
        run2_tool_ids = {d.tool_id for d in run2_registry.definitions()}
        assert "builtin.calculator" in run2_tool_ids
        assert any("static-server:add:" in tid for tid in run2_tool_ids)
        assert any("dynamic-server:add:" in tid for tid in run2_tool_ids)
        assert any("dynamic-server:multiply:" in tid for tid in run2_tool_ids)
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_manager_rolls_back_base_registry_when_later_server_fails(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    builtin_tool: Tool = _StubBuiltinTool("builtin.echo")
    registry.register(builtin_tool)

    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "dynamic-server": (
                    *_SERVER_COMMAND,
                    "--emit-tool-list-change",
                ),
                "failing-server": _EXITING_SERVER_COMMAND,
            },
        ),
        registry=registry,
    )

    try:
        await manager.start()

        assert manager.has_active_servers
        assert "failing-server" in manager.failed_servers
        assert "dynamic-server" not in manager.failed_servers

        tool_ids = {d.tool_id for d in registry.definitions()}
        assert "builtin.echo" in tool_ids
        assert any("dynamic-server:add:" in tid for tid in tool_ids)
    finally:
        await manager.aclose()


@pytest.mark.asyncio
async def test_session_and_manager_keep_last_valid_tools_if_refresh_fails(
    tmp_path: Path,
) -> None:
    registry = ToolRegistry()
    builtin_tool: Tool = _StubBuiltinTool("builtin.echo")
    registry.register(builtin_tool)

    manager = McpServerManager(
        configs=_configs(
            working_directory=tmp_path,
            servers={
                "flaky-dynamic-server": (
                    *_SERVER_COMMAND,
                    "--emit-tool-list-change",
                    "--fail-tool-list-on-refresh",
                ),
            },
        ),
        registry=registry,
    )

    try:
        await manager.start()

        # Initial startup succeeded with "add" tool
        tool_ids = {d.tool_id for d in registry.definitions()}
        assert "builtin.echo" in tool_ids
        assert any("flaky-dynamic-server:add:" in tid for tid in tool_ids)

        # Give time for failed refresh to run and be safely caught/discarded
        await asyncio.sleep(0.1)

        # Still contains previous valid tools intact
        tool_ids_after = {d.tool_id for d in registry.definitions()}
        assert tool_ids_after == tool_ids
    finally:
        await manager.aclose()
