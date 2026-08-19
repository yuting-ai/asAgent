from collections.abc import Callable
from dataclasses import dataclass, field
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
class SavedProviderConfigStatus:
    location: ProviderLocation
    model: str
    base_url: str
    api_key_saved: bool


@dataclass(frozen=True, slots=True)
class ModelSettingsStatus:
    configured: bool
    active: bool
    issue: "ModelSettingsIssue | None"
    location: ProviderLocation | None
    api_key_saved: bool
    model: str | None
    base_url: str | None
    saved_providers: dict[str, SavedProviderConfigStatus] = field(default_factory=dict)


class ModelApiKeyMissingError(RuntimeError):
    pass


class ModelSettingsIssue(StrEnum):
    API_KEY_MISSING = "api_key_missing"
    CREDENTIAL_STORE_UNAVAILABLE = "credential_store_unavailable"


def detect_provider_name(base_url: str, location: ProviderLocation) -> str:
    url_lower = base_url.strip().casefold()
    if "api.deepseek.com" in url_lower:
        return "deepseek"
    if "api.openai.com" in url_lower:
        return "openai"
    if "11434" in url_lower:
        return "ollama"
    if "1234" in url_lower:
        return "lmstudio"
    if "openrouter.ai" in url_lower:
        return "openrouter"
    if "siliconflow.cn" in url_lower:
        return "siliconflow"
    return "custom"


def provider_connection_id(provider_name: str) -> ConnectionId:
    return ConnectionId(f"connection-desktop-model-{provider_name}")


def provider_secret_id(provider_name: str) -> str:
    return f"desktop-model-api-key-{provider_name}"


class ModelSettings:
    """Coordinates desktop model profiles and their Keychain API keys."""

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
        active_profile = self._load_profile()
        api_key_saved = False
        issue: ModelSettingsIssue | None = None
        if active_profile is not None and active_profile.secret_id is not None:
            try:
                api_key_saved = (
                    self._credential_store.get_credential(MODEL_CONNECTION_ID)
                    is not None
                )
            except CredentialStoreError:
                issue = ModelSettingsIssue.CREDENTIAL_STORE_UNAVAILABLE
            if not api_key_saved and issue is None:
                issue = ModelSettingsIssue.API_KEY_MISSING

        saved_providers: dict[str, SavedProviderConfigStatus] = {}
        all_profiles = self._load_all_profiles()
        for name, p in all_profiles.items():
            if name == MODEL_PROFILE_NAME:
                continue
            key_saved = False
            if p.location is ProviderLocation.EXTERNAL:
                try:
                    p_key = self._credential_store.get_credential(
                        provider_connection_id(name)
                    )
                    if p_key is not None:
                        key_saved = True
                    elif (
                        active_profile is not None
                        and detect_provider_name(
                            str(active_profile.base_url), active_profile.location
                        )
                        == name
                    ):
                        key_saved = api_key_saved
                except CredentialStoreError:
                    key_saved = False
            saved_providers[name] = SavedProviderConfigStatus(
                location=p.location,
                model=p.model,
                base_url=str(p.base_url),
                api_key_saved=key_saved,
            )

        return ModelSettingsStatus(
            configured=active_profile is not None,
            active=active_profile is not None and issue is None,
            issue=issue,
            location=None if active_profile is None else active_profile.location,
            api_key_saved=api_key_saved,
            model=None if active_profile is None else active_profile.model,
            base_url=None if active_profile is None else str(active_profile.base_url),
            saved_providers=saved_providers,
        )

    async def save(
        self,
        *,
        location: ProviderLocation,
        model: str,
        base_url: str,
        api_key: str | None = None,
    ) -> ModelSettingsStatus:
        provider_name = detect_provider_name(base_url, location)
        p_conn_id = provider_connection_id(provider_name)
        p_secret_id = provider_secret_id(provider_name)

        saved_key = api_key
        if saved_key is None and location is ProviderLocation.EXTERNAL:
            saved_key = self._credential_store.get_credential(p_conn_id)
            if saved_key is None:
                saved_key = self._credential_store.get_credential(MODEL_CONNECTION_ID)
        if location is ProviderLocation.EXTERNAL and saved_key is None:
            raise ModelApiKeyMissingError("model api key is not saved")

        profile = ProviderConfig.model_validate(
            {
                "adapter": ProviderAdapter.OPENAI_COMPATIBLE,
                "location": location,
                "model": model,
                "base_url": base_url,
                "secret_id": p_secret_id if saved_key is not None else None,
            },
        )
        if api_key is not None:
            self._credential_store.save_credential(p_conn_id, api_key)
            self._credential_store.save_credential(MODEL_CONNECTION_ID, api_key)
        elif saved_key is not None:
            self._credential_store.save_credential(p_conn_id, saved_key)
            self._credential_store.save_credential(MODEL_CONNECTION_ID, saved_key)

        await self._save_connection(MODEL_CONNECTION_ID, account_label=profile.model)
        await self._save_connection(p_conn_id, account_label=profile.model)
        self._save_profile(provider_name, profile)
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

    def _load_all_profiles(self) -> dict[str, ProviderConfig]:
        try:
            profiles = load_provider_profiles(self._config_dir)
            return dict(profiles.providers)
        except ProviderConfigurationError as error:
            if not (self._config_dir / "providers.toml").exists():
                return {}
            raise error

    def _save_profile(self, provider_name: str, profile: ProviderConfig) -> None:
        profile_path = self._config_dir / "providers.toml"
        if profile_path.exists():
            providers = dict(load_provider_profiles(self._config_dir).providers)
        else:
            providers = {}
        providers[MODEL_PROFILE_NAME] = profile
        providers[provider_name] = profile
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

    async def _save_connection(
        self, connection_id: ConnectionId, *, account_label: str
    ) -> None:
        timestamp = self._clock()
        existing = await self._connections.get(connection_id)
        await self._connections.save(
            Connection(
                connection_id=connection_id,
                user_id=self._user_id if existing is None else existing.user_id,
                service_id="model-provider",
                account_label=account_label,
                granted_scopes=frozenset(),
                status=ConnectionStatus.ACTIVE,
                created_at=timestamp if existing is None else existing.created_at,
                updated_at=timestamp,
            ),
        )
