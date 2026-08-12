from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from asagent.core.connection import Connection, ConnectionStatus, CredentialStore
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.tools.mcp_config import (
    McpServerConfig,
    McpServerConfigs,
    load_mcp_server_configs,
    save_mcp_server_configs,
)

TAVILY_SERVER_NAME: Final = "tavily"
TAVILY_CONNECTION_ID: Final = ConnectionId("connection-tavily")
TAVILY_SERVICE_ID: Final = "tavily"
TAVILY_ACCOUNT_LABEL: Final = "Tavily Web Search"
TAVILY_CREDENTIAL_ENVIRONMENT_VARIABLE: Final = "TAVILY_API_KEY"
TAVILY_ALLOWED_TOOLS: Final = ("tavily_search",)
TAVILY_COMMAND: Final = ("npx", "-y", "tavily-mcp@latest")
_LOCAL_USER_ID: Final = UserId("local-user")


class TavilySettingsError(RuntimeError):
    pass


class TavilyApiKeyMissingError(TavilySettingsError):
    pass


@dataclass(frozen=True, slots=True)
class TavilySettingsStatus:
    enabled: bool
    api_key_saved: bool


class TavilySettings:
    """Coordinates Tavily API key, Connection metadata and MCP configuration."""

    def __init__(
        self,
        *,
        config_dir: Path,
        connections: ConnectionRepository,
        credential_store: CredentialStore,
        user_id: UserId = _LOCAL_USER_ID,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config_dir = config_dir
        self._connections = connections
        self._credential_store = credential_store
        self._user_id = user_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_status(self) -> TavilySettingsStatus:
        configs = load_mcp_server_configs(self._config_dir)
        return TavilySettingsStatus(
            enabled=TAVILY_SERVER_NAME in configs.servers,
            api_key_saved=(
                self._credential_store.get_credential(TAVILY_CONNECTION_ID) is not None
            ),
        )

    async def enable(self, *, api_key: str | None = None) -> TavilySettingsStatus:
        if api_key is not None:
            self._credential_store.save_credential(TAVILY_CONNECTION_ID, api_key)
        elif self._credential_store.get_credential(TAVILY_CONNECTION_ID) is None:
            raise TavilyApiKeyMissingError("tavily api key is not saved")

        await self._save_connection()
        self._write_tavily_server_config()
        return await self.get_status()

    async def disable(self) -> TavilySettingsStatus:
        self._remove_tavily_server_config()
        return await self.get_status()

    async def delete(self) -> TavilySettingsStatus:
        self._remove_tavily_server_config()
        self._credential_store.delete_credential(TAVILY_CONNECTION_ID)
        await self._connections.delete(TAVILY_CONNECTION_ID)
        return await self.get_status()

    async def _save_connection(self) -> None:
        timestamp = self._clock()
        existing = await self._connections.get(TAVILY_CONNECTION_ID)

        if existing is None:
            connection = Connection(
                connection_id=TAVILY_CONNECTION_ID,
                user_id=self._user_id,
                service_id=TAVILY_SERVICE_ID,
                account_label=TAVILY_ACCOUNT_LABEL,
                granted_scopes=frozenset(),
                status=ConnectionStatus.ACTIVE,
                created_at=timestamp,
                updated_at=timestamp,
            )
        else:
            connection = Connection(
                connection_id=existing.connection_id,
                user_id=existing.user_id,
                service_id=existing.service_id,
                account_label=existing.account_label,
                granted_scopes=existing.granted_scopes,
                status=ConnectionStatus.ACTIVE,
                created_at=existing.created_at,
                updated_at=timestamp,
            )

        await self._connections.save(connection)

    def _write_tavily_server_config(self) -> None:
        configs = load_mcp_server_configs(self._config_dir)
        servers = dict(configs.servers)
        servers[TAVILY_SERVER_NAME] = McpServerConfig(
            command=TAVILY_COMMAND,
            working_directory=self._config_dir.resolve(),
            connection_id=str(TAVILY_CONNECTION_ID),
            credential_environment_variable=TAVILY_CREDENTIAL_ENVIRONMENT_VARIABLE,
            allowed_tools=TAVILY_ALLOWED_TOOLS,
        )
        save_mcp_server_configs(
            self._config_dir,
            McpServerConfigs(servers=servers),
        )

    def _remove_tavily_server_config(self) -> None:
        configs = load_mcp_server_configs(self._config_dir)
        if TAVILY_SERVER_NAME not in configs.servers:
            return

        servers = dict(configs.servers)
        del servers[TAVILY_SERVER_NAME]
        save_mcp_server_configs(
            self._config_dir,
            McpServerConfigs(servers=servers),
        )
