import pytest
from pydantic import ValidationError

from asagent.models.config import (
    ProviderAdapter,
    ProviderConfig,
    ProviderProfiles,
)


def test_provider_profiles_support_openai_compatible_and_anthropic_adapters() -> None:
    profiles = ProviderProfiles.model_validate(
        {
            "providers": {
                "deepseek": {
                    "adapter": "openai_compatible",
                    "model": "deepseek-chat",
                    "base_url": "https://api.example.test/v1",
                    "secret_id": "deepseek_api_key",
                },
                "claude": {
                    "adapter": "anthropic_messages",
                    "model": "claude-example",
                    "base_url": "https://api.example.test",
                    "secret_id": "claude_api_key",
                    "timeout_seconds": 45,
                },
            }
        }
    )

    deepseek = profiles.providers["deepseek"]
    claude = profiles.providers["claude"]

    assert deepseek.adapter is ProviderAdapter.OPENAI_COMPATIBLE
    assert deepseek.model == "deepseek-chat"
    assert str(deepseek.base_url).startswith("https://api.example.test/")
    assert deepseek.timeout_seconds == 30.0

    assert claude.adapter is ProviderAdapter.ANTHROPIC_MESSAGES
    assert claude.timeout_seconds == 45.0


@pytest.mark.parametrize(
    "config",
    [
        {
            "adapter": "unsupported",
            "model": "example",
            "base_url": "https://api.example.test",
            "secret_id": "example_key",
        },
        {
            "adapter": "openai_compatible",
            "model": " ",
            "base_url": "https://api.example.test",
            "secret_id": "example_key",
        },
        {
            "adapter": "openai_compatible",
            "model": "example",
            "base_url": "https://api.example.test",
            "secret_id": "example_key",
            "timeout_seconds": 0,
        },
    ],
)
def test_provider_config_rejects_invalid_values(
    config: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ProviderConfig.model_validate(config)


def test_provider_profiles_reject_empty_profile_names() -> None:
    with pytest.raises(ValidationError):
        ProviderProfiles.model_validate(
            {
                "providers": {
                    "": {
                        "adapter": "openai_compatible",
                        "model": "example",
                        "base_url": "https://api.example.test",
                        "secret_id": "example_key",
                    }
                }
            }
        )
