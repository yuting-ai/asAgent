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
      "working_directory": "/opt/mcp",
      "connection_id": "connection-test",
      "credential_environment_variable": "TEST_MCP_TOKEN",
      "allowed_tools": ["tavily-search"]
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
        connection_id="connection-test",
        credential_environment_variable="TEST_MCP_TOKEN",
        allowed_tools=("tavily-search",),
    )


def test_allowed_tools_may_be_omitted_for_full_import() -> None:
    config = McpServerConfig.model_validate(
        {
            "command": ["python"],
            "working_directory": "/opt/mcp",
        }
    )

    assert config.allowed_tools is None


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
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "connection_id": "connection-1",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "credential_environment_variable": "TEST_TOKEN",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "connection_id": "connection-1",
                    "credential_environment_variable": "invalid-name",
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "allowed_tools": [],
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "allowed_tools": ["search", "search"],
                }
            }
        },
        {
            "servers": {
                "test-server": {
                    "command": ["python"],
                    "working_directory": "/opt/mcp",
                    "allowed_tools": [""],
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


def test_normalize_subprocess_path_augments_macos_gui_path() -> None:
    from asagent.cli import _mcp_subprocess_environment, _normalize_subprocess_path

    # Minimal macOS GUI PATH without Homebrew
    minimal_gui_path = "/usr/bin:/bin:/usr/sbin:/sbin"
    normalized = _normalize_subprocess_path(minimal_gui_path, platform_name="darwin")

    assert "/opt/homebrew/bin" in normalized
    assert "/usr/local/bin" in normalized
    assert "/usr/bin" in normalized
    # Check no duplicate segments
    parts = normalized.split(":")
    assert len(parts) == len(set(parts))

    # Test _mcp_subprocess_environment includes normalized PATH
    env = _mcp_subprocess_environment({"PATH": minimal_gui_path})
    assert "/opt/homebrew/bin" in env["PATH"]


def test_normalize_subprocess_path_preserves_linux_path() -> None:
    from asagent.cli import _normalize_subprocess_path

    linux_path = "/custom/bin:/usr/bin"
    normalized = _normalize_subprocess_path(linux_path, platform_name="linux")
    assert normalized == linux_path
