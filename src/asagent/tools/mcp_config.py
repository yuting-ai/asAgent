import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_SERVER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class McpConfigurationError(RuntimeError):
    pass


class McpServerConfig(BaseModel):
    """Non-sensitive configuration for one stdio MCP server."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )

    command: tuple[str, ...] = Field(min_length=1)
    working_directory: Path

    @field_validator("command")
    @classmethod
    def validate_command(cls, command: tuple[str, ...]) -> tuple[str, ...]:
        if any(not part for part in command):
            raise ValueError("MCP server command arguments must not be empty")
        return command

    @field_validator("working_directory")
    @classmethod
    def validate_working_directory(cls, directory: Path) -> Path:
        if not directory.is_absolute():
            raise ValueError("MCP server working_directory must be absolute")
        return directory


class McpServerConfigs(BaseModel):
    """All non-sensitive MCP server configurations."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    servers: dict[str, McpServerConfig] = Field(default_factory=dict)

    @field_validator("servers")
    @classmethod
    def validate_server_names(
        cls,
        servers: dict[str, McpServerConfig],
    ) -> dict[str, McpServerConfig]:
        if any(not _SERVER_NAME_PATTERN.fullmatch(name) for name in servers):
            raise ValueError("MCP server names must be lowercase identifiers")
        return servers


def load_mcp_server_configs(config_dir: Path) -> McpServerConfigs:
    """Load optional non-sensitive MCP configuration from config_dir/mcp.json."""

    config_path = config_dir / "mcp.json"

    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return McpServerConfigs()
    except OSError as error:
        raise McpConfigurationError(
            "MCP configuration file is unavailable",
        ) from error

    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise McpConfigurationError(
            "MCP configuration is invalid JSON",
        ) from error

    try:
        return McpServerConfigs.model_validate(data)
    except ValidationError as error:
        raise McpConfigurationError(
            "MCP configuration is invalid",
        ) from error
