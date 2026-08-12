from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from asagent.core.connection import Connection, ConnectionStatus, CredentialStore
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.models.config import ProviderAdapter, ProviderConfig, ProviderProfiles
from asagent.models.errors import ProviderConfigurationError
from asagent.models.profile_loader import load_provider_profiles, save_provider_profiles

MODEL_PROFILE_NAME: Final = "desktop"
MODEL_SECRET_ID: Final = "desktop-model-api-key"
MODEL_CONNECTION_ID: Final = ConnectionId("connection-desktop-model")
_LOCAL_USER_ID: Final = UserId("local-user")


@dataclass(frozen=True, slots=True)
class ModelSettingsStatus:
    configured: bool
    api_key_saved: bool
    model: str | None
    base_url: str | None


class ModelApiKeyMissingError(RuntimeError):
    pass


class ModelSettings:
    """Coordinates the single desktop model profile and its Keychain API key."""

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

    async def get_status(self) -> ModelSettingsStatus:
        profile = self._load_profile()
        return ModelSettingsStatus(
            configured=profile is not None,
            api_key_saved=(
                self._credential_store.get_credential(MODEL_CONNECTION_ID) is not None
            ),
            model=None if profile is None else profile.model,
            base_url=None if profile is None else str(profile.base_url),
        )

    async def save(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None = None,
    ) -> ModelSettingsStatus:
        profile = ProviderConfig.model_validate(
            {
                "adapter": ProviderAdapter.OPENAI_COMPATIBLE,
                "model": model,
                "base_url": base_url,
                "secret_id": MODEL_SECRET_ID,
            },
        )
        if api_key is not None:
            self._credential_store.save_credential(MODEL_CONNECTION_ID, api_key)
        elif self._credential_store.get_credential(MODEL_CONNECTION_ID) is None:
            raise ModelApiKeyMissingError("model api key is not saved")
        await self._save_connection(account_label=profile.model)
        self._save_profile(profile)
        return await self.get_status()

    async def delete(self) -> ModelSettingsStatus:
        self._remove_profile()
        self._credential_store.delete_credential(MODEL_CONNECTION_ID)
        await self._connections.delete(MODEL_CONNECTION_ID)
        return await self.get_status()

    def get_active_profile(self) -> ProviderConfig | None:
        profile = self._load_profile()
        if profile is None:
            return None
        if self._credential_store.get_credential(MODEL_CONNECTION_ID) is None:
            return None
        return profile

    def _load_profile(self) -> ProviderConfig | None:
        try:
            profiles = load_provider_profiles(self._config_dir)
        except ProviderConfigurationError as error:
            if not (self._config_dir / "providers.toml").exists():
                return None
            raise error
        return profiles.providers.get(MODEL_PROFILE_NAME)

    def _save_profile(self, profile: ProviderConfig) -> None:
        profile_path = self._config_dir / "providers.toml"
        if profile_path.exists():
            providers = dict(load_provider_profiles(self._config_dir).providers)
        else:
            providers = {}
        providers[MODEL_PROFILE_NAME] = profile
        save_provider_profiles(self._config_dir, ProviderProfiles(providers=providers))

    def _remove_profile(self) -> None:
        profile_path = self._config_dir / "providers.toml"
        if not profile_path.exists():
            return
        profiles = load_provider_profiles(self._config_dir)
        providers = dict(profiles.providers)
        if MODEL_PROFILE_NAME not in providers:
            return
        del providers[MODEL_PROFILE_NAME]
        if providers:
            save_provider_profiles(
                self._config_dir, ProviderProfiles(providers=providers)
            )
        else:
            profile_path.unlink()

    async def _save_connection(self, *, account_label: str) -> None:
        timestamp = self._clock()
        existing = await self._connections.get(MODEL_CONNECTION_ID)
        await self._connections.save(
            Connection(
                connection_id=MODEL_CONNECTION_ID,
                user_id=self._user_id if existing is None else existing.user_id,
                service_id="model-provider",
                account_label=account_label,
                granted_scopes=frozenset(),
                status=ConnectionStatus.ACTIVE,
                created_at=timestamp if existing is None else existing.created_at,
                updated_at=timestamp,
            ),
        )
