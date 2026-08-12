from datetime import UTC, datetime
from pathlib import Path

import pytest

from asagent.bootstrap.model_settings import (
    MODEL_CONNECTION_ID,
    MODEL_PROFILE_NAME,
    ModelSettings,
)
from asagent.core.connection import Connection, CredentialStore
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.models.config import ProviderAdapter, ProviderConfig, ProviderProfiles
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
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="secret-model-key",
    )

    assert status.configured is True
    assert status.api_key_saved is True
    assert status.model == "deepseek-chat"
    assert status.base_url == "https://api.deepseek.com/v1"
    assert credentials.get_credential(MODEL_CONNECTION_ID) == "secret-model-key"
    assert await connections.get(MODEL_CONNECTION_ID) is not None
    assert set(load_provider_profiles(config_dir).providers) == {
        "other",
        MODEL_PROFILE_NAME,
    }
    assert "secret-model-key" not in (config_dir / "providers.toml").read_text(
        encoding="utf-8"
    )
    assert settings.get_active_profile() is not None


@pytest.mark.asyncio
async def test_delete_removes_only_desktop_profile_key_and_connection(
    tmp_path: Path,
) -> None:
    settings, credentials, connections = _settings(tmp_path)
    await settings.save(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key="secret-model-key",
    )

    status = await settings.delete()

    assert status.configured is False
    assert status.api_key_saved is False
    assert credentials.get_credential(MODEL_CONNECTION_ID) is None
    assert await connections.get(MODEL_CONNECTION_ID) is None
    assert settings.get_active_profile() is None
