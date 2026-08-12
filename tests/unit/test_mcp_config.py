from pathlib import Path

import pytest
from pydantic import ValidationError

from asagent.tools.mcp_config import (
    McpConfigurationError,
    McpServerConfig,
    McpServerConfigs,
    load_mcp_server_configs,
)


def test_load_mcp_server_configs_from_json(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "mcp.json").write_text(
        """
{
  "servers": {
    "test-server": {
      "command": ["python", "-u", "/opt/mcp/server.py"],
      "working_directory": "/opt/mcp"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )

    configs = load_mcp_server_configs(config_dir)

    assert configs.servers["test-server"] == McpServerConfig(
        command=("python", "-u", "/opt/mcp/server.py"),
        working_directory=Path("/opt/mcp"),
    )


def test_missing_mcp_configuration_means_no_servers(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"

    assert load_mcp_server_configs(config_dir) == McpServerConfigs()
    assert not config_dir.exists()


@pytest.mark.parametrize(
    "data",
    [
        {
            "servers": {
                "Test Server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python", ""],
                    "working_directory": "/opt/mcp",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "relative/path",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "token": "must-not-be-here",
                }
            }
        },
    ],
)
def test_mcp_server_configs_reject_unsafe_or_invalid_data(
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        McpServerConfigs.model_validate(data)


def test_invalid_json_becomes_configuration_error(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "mcp.json").write_text("{", encoding="utf-8")

    with pytest.raises(McpConfigurationError, match="invalid JSON"):
        load_mcp_server_configs(config_dir)
