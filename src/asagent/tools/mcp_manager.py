import asyncio
from collections.abc import Mapping

from asagent.core.connection import CredentialStore
from asagent.core.ids import ConnectionId
from asagent.tools.mcp import McpClient, McpServerSession
from asagent.tools.mcp_config import McpServerConfig, McpServerConfigs
from asagent.tools.registry import ToolRegistry


class McpServerCredentialError(RuntimeError):
    """A configured MCP server credential could not be supplied safely."""


class McpServerManager:
    """Owns configured MCP sessions and imports tools atomically."""

    def __init__(
        self,
        *,
        configs: McpServerConfigs,
        registry: ToolRegistry,
        environment: Mapping[str, str] | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._configs = configs
        self._target_registry = registry
        self._base_registry = registry.copy()
        self._environment = {} if environment is None else dict(environment)
        self._credential_store = credential_store
        self._sessions: list[McpServerSession] = []
        self._failed_servers: dict[str, str] = {}
        self._recompose_lock = asyncio.Lock()
        self._started = False
        self._closed = False

    @property
    def failed_servers(self) -> Mapping[str, str]:
        return dict(self._failed_servers)

    @property
    def active_server_count(self) -> int:
        return len(self._sessions)

    @property
    def has_active_servers(self) -> bool:
        return bool(self._sessions)

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("MCP server manager is closed")
        if self._started:
            raise RuntimeError("MCP server manager is already started")

        self._failed_servers.clear()

        try:
            for server_name, config in self._configs.servers.items():
                try:
                    server_env = self._environment_for(config)
                except Exception as error:
                    self._failed_servers[server_name] = str(error)
                    continue

                session = McpServerSession(
                    client=McpClient(
                        command=config.command,
                        working_directory=config.working_directory,
                        environment=server_env,
                    ),
                    server_name=server_name,
                    allowed_tools=config.allowed_tools,
                    on_registry_updated=self._recompose_registry,
                )
                try:
                    await session.start()
                    self._sessions.append(session)
                except Exception as error:
                    self._failed_servers[server_name] = str(error)
                    await session.aclose()
                    continue

            self._started = True
            await self._recompose_registry()
        except BaseException:
            self._target_registry.replace_with(self._base_registry)
            await self.aclose()
            raise

    async def _recompose_registry(self) -> None:
        if not self._started:
            return

        async with self._recompose_lock:
            composite = self._base_registry.copy()
            existing_tool_ids = {
                definition.tool_id for definition in composite.definitions()
            }

            for session in self._sessions:
                for definition in session.registry.definitions():
                    if definition.tool_id in existing_tool_ids:
                        raise ValueError(
                            f"MCP tool_id is already registered: {definition.tool_id}",
                        )
                    tool = session.registry.get(definition.tool_id)
                    composite.register(tool)
                    existing_tool_ids.add(definition.tool_id)

            self._target_registry.replace_with(composite)

    async def aclose(self) -> None:
        if self._closed:
            return

        self._closed = True
        sessions = tuple(reversed(self._sessions))
        self._sessions.clear()
        await asyncio.gather(*(session.aclose() for session in sessions))

    def _environment_for(
        self,
        config: McpServerConfig,
    ) -> dict[str, str]:
        environment = dict(self._environment)

        if not config.requires_credential:
            return environment

        if self._credential_store is None:
            raise McpServerCredentialError(
                "MCP credential storage is unavailable",
            )

        connection_id = config.connection_id
        environment_variable = config.credential_environment_variable
        if connection_id is None or environment_variable is None:
            raise McpServerCredentialError(
                "MCP credential configuration is incomplete",
            )

        credential = self._credential_store.get_credential(
            ConnectionId(connection_id),
        )
        if credential is None:
            raise McpServerCredentialError(
                "MCP server credential is unavailable",
            )

        environment[environment_variable] = credential
        return environment
