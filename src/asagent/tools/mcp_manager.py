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
    """Owns configured MCP sessions and imports tools only after full startup."""

    def __init__(
        self,
        *,
        configs: McpServerConfigs,
        registry: ToolRegistry,
        environment: Mapping[str, str] | None = None,
        credential_store: CredentialStore | None = None,
    ) -> None:
        self._configs = configs
        self._registry = registry
        self._environment = {} if environment is None else dict(environment)
        self._credential_store = credential_store
        self._sessions: list[McpServerSession] = []
        self._started = False
        self._closed = False

    async def start(self) -> None:
        if self._closed:
            raise RuntimeError("MCP server manager is closed")
        if self._started:
            raise RuntimeError("MCP server manager is already started")

        staging_registry = ToolRegistry()

        try:
            for server_name, config in self._configs.servers.items():
                session = McpServerSession(
                    client=McpClient(
                        command=config.command,
                        working_directory=config.working_directory,
                        environment=self._environment_for(config),
                    ),
                    registry=staging_registry,
                    server_name=server_name,
                )
                self._sessions.append(session)
                await session.start()

            existing_tool_ids = {
                definition.tool_id for definition in self._registry.definitions()
            }
            staged_definitions = staging_registry.definitions()
            if any(
                definition.tool_id in existing_tool_ids
                for definition in staged_definitions
            ):
                raise ValueError("MCP tool_id is already registered")

            for definition in staged_definitions:
                self._registry.register(staging_registry.get(definition.tool_id))
        except BaseException:
            await self.aclose()
            raise

        self._started = True

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
