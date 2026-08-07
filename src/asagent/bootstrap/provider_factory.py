import httpx

from asagent.models.config import (
    ProviderAdapter,
    ProviderProfiles,
)
from asagent.models.errors import ProviderConfigurationError
from asagent.models.openai_compatible_provider import OpenAICompatibleProvider
from asagent.models.provider import ModelProvider
from asagent.models.secrets import SecretProvider


def create_model_provider(
    *,
    profiles: ProviderProfiles,
    profile_name: str,
    secrets: SecretProvider,
    http_client: httpx.AsyncClient,
) -> ModelProvider:
    try:
        config = profiles.providers[profile_name]
    except KeyError as error:
        raise ProviderConfigurationError(
            "requested provider profile is unavailable",
        ) from error

    if config.adapter is ProviderAdapter.OPENAI_COMPATIBLE:
        return OpenAICompatibleProvider(
            config=config,
            secrets=secrets,
            http_client=http_client,
        )

    raise ProviderConfigurationError(
        "requested provider adapter is not implemented",
    )
