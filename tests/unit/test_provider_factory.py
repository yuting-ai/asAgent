import httpx
import pytest

from ragent.bootstrap.provider_factory import create_model_provider
from ragent.models.config import ProviderProfiles
from ragent.models.errors import ProviderConfigurationError
from ragent.models.openai_compatible_provider import OpenAICompatibleProvider


class InMemorySecretProvider:
    def get_secret(self, secret_id: str) -> str | None:
        return "value-from-secret-store"


def make_profiles() -> ProviderProfiles:
    return ProviderProfiles.model_validate(
        {
            "providers": {
                "deepseek": {
                    "adapter": "openai_compatible",
                    "model": "deepseek-test",
                    "base_url": "https://api.example.test/v1",
                    "secret_id": "deepseek_api_key",
                },
                "claude": {
                    "adapter": "anthropic_messages",
                    "model": "claude-test",
                    "base_url": "https://api.example.test",
                    "secret_id": "claude_api_key",
                },
            }
        }
    )


@pytest.mark.asyncio
async def test_factory_creates_openai_compatible_provider() -> None:
    async with httpx.AsyncClient() as client:
        provider = create_model_provider(
            profiles=make_profiles(),
            profile_name="deepseek",
            secrets=InMemorySecretProvider(),
            http_client=client,
        )

    assert isinstance(provider, OpenAICompatibleProvider)


@pytest.mark.asyncio
async def test_factory_rejects_missing_profile() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(
            ProviderConfigurationError,
            match="profile is unavailable",
        ):
            create_model_provider(
                profiles=make_profiles(),
                profile_name="missing",
                secrets=InMemorySecretProvider(),
                http_client=client,
            )


@pytest.mark.asyncio
async def test_factory_rejects_unimplemented_adapter() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(
            ProviderConfigurationError,
            match="adapter is not implemented",
        ):
            create_model_provider(
                profiles=make_profiles(),
                profile_name="claude",
                secrets=InMemorySecretProvider(),
                http_client=client,
            )
