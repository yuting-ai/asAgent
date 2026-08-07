from pathlib import Path

import pytest

from ragent.models.errors import ProviderConfigurationError
from ragent.models.profile_loader import load_provider_profiles


def write_profiles(config_dir: Path) -> None:
    config_dir.mkdir()
    (config_dir / "providers.toml").write_text(
        """
[providers.deepseek]
adapter = "openai_compatible"
model = "deepseek-test"
base_url = "https://api.example.test/v1"
secret_id = "deepseek_api_key"
timeout_seconds = 12

[providers.claude]
adapter = "anthropic_messages"
model = "claude-test"
base_url = "https://api.example.test"
secret_id = "claude_api_key"
""".strip(),
        encoding="utf-8",
    )


def test_load_provider_profiles_from_toml(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    write_profiles(config_dir)

    profiles = load_provider_profiles(config_dir)

    assert profiles.providers["deepseek"].model == "deepseek-test"
    assert profiles.providers["deepseek"].timeout_seconds == 12
    assert profiles.providers["claude"].adapter == "anthropic_messages"


def test_missing_profile_file_does_not_create_configuration_directory(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"

    with pytest.raises(
        ProviderConfigurationError,
        match="configuration file is unavailable",
    ):
        load_provider_profiles(config_dir)

    assert not config_dir.exists()


def test_invalid_toml_becomes_configuration_error(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.toml").write_text(
        "[providers.deepseek",
        encoding="utf-8",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="invalid TOML",
    ):
        load_provider_profiles(config_dir)


def test_invalid_profile_data_becomes_configuration_error(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.toml").write_text(
        """
[providers.deepseek]
adapter = "openai_compatible"
model = "deepseek-test"
base_url = "https://api.example.test"
secret_id = "deepseek_api_key"
unexpected_option = true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ProviderConfigurationError,
        match="configuration is invalid",
    ):
        load_provider_profiles(config_dir)
