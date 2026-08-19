from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final

from asagent.bootstrap.keychain_credential_store import CredentialStoreError
from asagent.core.connection import Connection, ConnectionStatus, CredentialStore
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.models.config import (
    ProviderAdapter,
    ProviderConfig,
    ProviderLocation,
    ProviderProfiles,
)
from asagent.models.errors import ProviderConfigurationError
from asagent.models.profile_loader import load_provider_profiles, save_provider_profiles

MODEL_PROFILE_NAME: Final = "desktop"
MODEL_SECRET_ID: Final = "desktop-model-api-key"
MODEL_CONNECTION_ID: Final = ConnectionId("connection-desktop-model")
_LOCAL_USER_ID: Final = UserId("local-user")


@dataclass(frozen=True, slots=True)
class ModelSettingsStatus:
    configured: bool
    active: bool
    issue: "ModelSettingsIssue | None"
    location: ProviderLocation | None
    api_key_saved: bool
    model: str | None
    base_url: str | None


class ModelApiKeyMissingError(RuntimeError):
    pass


class ModelSettingsIssue(StrEnum):
    API_KEY_MISSING = "api_key_missing"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"


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
        api_key_saved = False
        issue: ModelSettingsIssue | None = None
        if profile is not None and profile.secret_id is not None:
            try:
                api_key_saved = (
                    self._credential_store.get_credential(MODEL_CONNECTION_ID)
                    is not None
                )
            except CredentialStoreError:
                issue = ModelSettingsIssue.CREDENTIAL_STORE_UNAVAILABLE
            if not api_key_saved and issue is None:
                issue = ModelSettingsIssue.API_KEY_MISSING

        return ModelSettingsStatus(
            configured=profile is not None,
            active=profile is not None and issue is None,
            issue=issue,
            location=None if profile is None else profile.location,
            api_key_saved=api_key_saved,
            model=None if profile is None else profile.model,
            base_url=None if profile is None else str(profile.base_url),
        )

    async def save(
        self,
        *,
        location: ProviderLocation,
        model: str,
        base_url: str,
        api_key: str | None = None,
    ) -> ModelSettingsStatus:
        saved_key = api_key
        if saved_key is None and location is ProviderLocation.EXTERNAL:
            saved_key = self._credential_store.get_credential(MODEL_CONNECTION_ID)
        if location is ProviderLocation.EXTERNAL and saved_key is None:
            raise ModelApiKeyMissingError("model api key is not saved")

        profile = ProviderConfig.model_validate(
            {
                "adapter": ProviderAdapter.OPENAI_COMPATIBLE,
                "location": location,
                "model": model,
                "base_url": base_url,
                "secret_id": MODEL_SECRET_ID if saved_key is not None else None,
            },
        )
        if api_key is not None:
            self._credential_store.save_credential(MODEL_CONNECTION_ID, api_key)
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
        if profile.secret_id is not None:
            try:
                if self._credential_store.get_credential(MODEL_CONNECTION_ID) is None:
                    return None
            except CredentialStoreError:
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
