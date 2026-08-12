import json
import re
from pathlib import Path
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

_SERVER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ENVIRONMENT_VARIABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
    connection_id: str | None = None
    credential_environment_variable: str | None = None

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

    @field_validator("connection_id")
    @classmethod
    def validate_connection_id(
        cls,
        connection_id: str | None,
    ) -> str | None:
        if connection_id == "":
            raise ValueError("MCP connection_id must not be empty")
        return connection_id

    @field_validator("credential_environment_variable")
    @classmethod
    def validate_credential_environment_variable(
        cls,
        environment_variable: str | None,
    ) -> str | None:
        if (
            environment_variable is not None
            and not _ENVIRONMENT_VARIABLE_PATTERN.fullmatch(
                environment_variable,
            )
        ):
            raise ValueError(
                "MCP credential_environment_variable is invalid",
            )
        return environment_variable

    @model_validator(mode="after")
    def validate_credential_reference(self) -> Self:
        if (self.connection_id is None) != (
            self.credential_environment_variable is None
        ):
            raise ValueError(
                "MCP connection_id and credential_environment_variable "
                "must be provided together",
            )
        return self

    @property
    def requires_credential(self) -> bool:
        return self.connection_id is not None


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
