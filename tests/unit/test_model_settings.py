from datetime import UTC, datetime
from pathlib import Path

import pytest

from asagent.bootstrap.model_settings import (
    MODEL_CONNECTION_ID,
    MODEL_PROFILE_NAME,
    ModelSettings,
    ModelSettingsIssue,
)
from asagent.core.connection import Connection, CredentialStore
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.models.config import (
    ProviderAdapter,
    ProviderConfig,
    ProviderLocation,
    ProviderProfiles,
)
from asagent.models.profile_loader import load_provider_profiles, save_provider_profiles

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


class InMemoryCredentialStore(CredentialStore):
    def __init__(self) -> None:
        self.credentials: dict[ConnectionId, str] = {}

    def get_credential(self, connection_id: ConnectionId) -> str | None:
        return self.credentials.get(connection_id)

    def save_credential(self, connection_id: ConnectionId, credential: str) -> None:
        self.credentials[connection_id] = credential

    def delete_credential(self, connection_id: ConnectionId) -> None:
        self.credentials.pop(connection_id, None)


class InMemoryConnectionRepository(ConnectionRepository):
    def __init__(self) -> None:
        self.connections: dict[ConnectionId, Connection] = {}

    async def get(self, connection_id: ConnectionId) -> Connection | None:
        return self.connections.get(connection_id)

    async def list_for_user(self, user_id: UserId) -> tuple[Connection, ...]:
        return tuple(
            connection
            for connection in self.connections.values()
            if connection.user_id == user_id
        )

    async def save(self, connection: Connection) -> None:
        self.connections[connection.connection_id] = connection

    async def delete(self, connection_id: ConnectionId) -> bool:
        return self.connections.pop(connection_id, None) is not None


def _settings(
    tmp_path: Path,
) -> tuple[ModelSettings, InMemoryCredentialStore, InMemoryConnectionRepository]:
    credentials = InMemoryCredentialStore()
    connections = InMemoryConnectionRepository()
    return (
        ModelSettings(
            config_dir=tmp_path / "config",
            connections=connections,
            credential_store=credentials,
            clock=lambda: _NOW,
        ),
        credentials,
        connections,
    )


@pytest.mark.asyncio
async def test_save_keeps_key_out_of_provider_config_and_preserves_other_profiles(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config"
    save_provider_profiles(
        config_dir,
        ProviderProfiles(
            providers={
                "other": ProviderConfig.model_validate(
                    {
                        "adapter": ProviderAdapter.OPENAI_COMPATIBLE,
                        "model": "other-model",
                        "base_url": "https://example.com/v1",
                        "secret_id": "other-key",
                    },
                ),
            },
        ),
    )
    settings, credentials, connections = _settings(tmp_path)

    status = await settings.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="secret-model-key",
    )

    assert status.configured is True
    assert status.active is True
    assert status.issue is None
    assert status.location is ProviderLocation.EXTERNAL
    assert status.api_key_saved is True
    assert status.model == "deepseek-chat"
    assert status.base_url == "https://api.deepseek.com/v1"
    assert credentials.get_credential(MODEL_CONNECTION_ID) == "secret-model-key"
    assert await connections.get(MODEL_CONNECTION_ID) is not None
    assert set(load_provider_profiles(config_dir).providers) == {
        "other",
        "deepseek",
        MODEL_PROFILE_NAME,
    }
    assert "secret-model-key" not in (config_dir / "providers.toml").read_text(
        encoding="utf-8"
    )
    assert settings.get_active_profile() is not None

    reloaded = ModelSettings(
        config_dir=config_dir,
        connections=connections,
        credential_store=credentials,
        clock=lambda: _NOW,
    )
    reloaded_status = await reloaded.get_status()
    assert reloaded_status.location is ProviderLocation.EXTERNAL
    assert reloaded_status.active is True
    assert "deepseek" in reloaded_status.saved_providers
    assert reloaded_status.saved_providers["deepseek"].model == "deepseek-chat"
    assert reloaded_status.saved_providers["deepseek"].api_key_saved is True


@pytest.mark.asyncio
async def test_switching_between_multiple_providers_preserves_all_configs_and_keys(
    tmp_path: Path,
) -> None:
    settings, credentials, _connections = _settings(tmp_path)

    # 1. Save DeepSeek with key
    status1 = await settings.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="deepseek-secret-key",
    )
    assert status1.saved_providers["deepseek"].model == "deepseek-chat"
    assert status1.saved_providers["deepseek"].api_key_saved is True

    # 2. Save Ollama (local) without key
    status2 = await settings.save(
        location=ProviderLocation.LOCAL,
        model="qwen2.5:7b",
        base_url="http://127.0.0.1:11434/v1",
    )
    assert status2.location is ProviderLocation.LOCAL
    assert status2.model == "qwen2.5:7b"
    assert status2.saved_providers["ollama"].model == "qwen2.5:7b"
    assert status2.saved_providers["deepseek"].model == "deepseek-chat"
    assert status2.saved_providers["deepseek"].api_key_saved is True

    # 3. Switch back to DeepSeek without re-typing API key
    status3 = await settings.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
    )
    assert status3.location is ProviderLocation.EXTERNAL
    assert status3.active is True
    assert status3.api_key_saved is True
    assert status3.saved_providers["ollama"].model == "qwen2.5:7b"
    assert status3.saved_providers["deepseek"].model == "deepseek-chat"


@pytest.mark.asyncio
async def test_restart_between_saves_preserves_deepseek_key(
    tmp_path: Path,
) -> None:
    """Simulate: save DeepSeek → restart → save Ollama → restart → switch back.

    Credentials and config_dir persist across restarts; ModelSettings is re-created
    each time (like the real app does).
    """
    config_dir = tmp_path / "config"
    credentials = InMemoryCredentialStore()
    connections = InMemoryConnectionRepository()

    def make_settings() -> ModelSettings:
        return ModelSettings(
            config_dir=config_dir,
            connections=connections,
            credential_store=credentials,
            clock=lambda: _NOW,
        )

    # ── Session 1: save DeepSeek with API key ──
    s1 = make_settings()
    await s1.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="deepseek-secret-key",
    )

    # ── Session 2 (restart): save Ollama (local, no key) ──
    s2 = make_settings()
    status_before_save = await s2.get_status()
    assert status_before_save.saved_providers["deepseek"].api_key_saved is True, (
        "DeepSeek key should be visible after restart, before saving Ollama"
    )

    await s2.save(
        location=ProviderLocation.LOCAL,
        model="qwen2.5:7b",
        base_url="http://127.0.0.1:11434/v1",
    )

    # ── Session 3 (restart): get_status and check DeepSeek key is still there ──
    s3 = make_settings()
    status3 = await s3.get_status()
    assert status3.location is ProviderLocation.LOCAL
    assert status3.model == "qwen2.5:7b"
    assert "deepseek" in status3.saved_providers, (
        "DeepSeek profile must survive in providers.toml across restarts"
    )
    assert status3.saved_providers["deepseek"].api_key_saved is True, (
        "DeepSeek API key must remain in credential store after saving Ollama"
    )


@pytest.mark.asyncio
async def test_delete_removes_only_desktop_profile_key_and_connection(
    tmp_path: Path,
) -> None:
    settings, credentials, connections = _settings(tmp_path)
    await settings.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="secret-model-key",
    )

    status = await settings.delete()

    assert status.configured is False
    assert status.active is False
    assert status.issue is None
    assert status.api_key_saved is False
    assert credentials.get_credential(MODEL_CONNECTION_ID) is None
    assert await connections.get(MODEL_CONNECTION_ID) is None
    assert settings.get_active_profile() is None


@pytest.mark.asyncio
async def test_local_model_can_be_saved_and_activated_without_api_key(
    tmp_path: Path,
) -> None:
    settings, credentials, _connections = _settings(tmp_path)

    status = await settings.save(
        location=ProviderLocation.LOCAL,
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
    )

    assert status.configured is True
    assert status.active is True
    assert status.issue is None
    assert status.location is ProviderLocation.LOCAL
    assert status.api_key_saved is False
    assert credentials.get_credential(MODEL_CONNECTION_ID) is None
    profile = settings.get_active_profile()
    assert profile is not None
    assert profile.secret_id is None


@pytest.mark.asyncio
async def test_switching_to_local_without_a_key_does_not_reuse_external_key(
    tmp_path: Path,
) -> None:
    settings, credentials, _connections = _settings(tmp_path)
    await settings.save(
        location=ProviderLocation.EXTERNAL,
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="external-secret",
    )

    status = await settings.save(
        location=ProviderLocation.LOCAL,
        model="qwen3:8b",
        base_url="http://127.0.0.1:11434/v1",
    )

    assert status.active is True
    assert status.api_key_saved is False
    assert credentials.get_credential(MODEL_CONNECTION_ID) == "external-secret"
    profile = settings.get_active_profile()
    assert profile is not None
    assert profile.secret_id is None


@pytest.mark.asyncio
async def test_external_profile_with_missing_saved_key_is_configured_but_inactive(
    tmp_path: Path,
) -> None:
    settings, _credentials, _connections = _settings(tmp_path)
    config_dir = tmp_path / "config"
    save_provider_profiles(
        config_dir,
        ProviderProfiles(
            providers={
                MODEL_PROFILE_NAME: ProviderConfig.model_validate(
                    {
                        "adapter": ProviderAdapter.OPENAI_COMPATIBLE,
                        "location": ProviderLocation.EXTERNAL,
                        "model": "deepseek-chat",
                        "base_url": "https://api.deepseek.com/v1",
                        "secret_id": "desktop-model-api-key",
                    }
                )
            }
        ),
    )

    status = await settings.get_status()

    assert status.configured is True
    assert status.active is False
    assert status.issue is ModelSettingsIssue.API_KEY_MISSING
    assert status.location is ProviderLocation.EXTERNAL
    assert status.api_key_saved is False
    assert settings.get_active_profile() is None
