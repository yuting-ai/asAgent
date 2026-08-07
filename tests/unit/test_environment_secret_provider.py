from ragent.bootstrap.environment_secret_provider import (
    EnvironmentSecretProvider,
)
from ragent.models.secrets import SecretProvider


def test_environment_secret_provider_uses_explicit_binding() -> None:
    provider: SecretProvider = EnvironmentSecretProvider(
        environment={
            "RAGENT_DEEPSEEK_API_KEY": "development-secret-value",
        },
        bindings={
            "deepseek_api_key": "RAGENT_DEEPSEEK_API_KEY",
        },
    )

    assert provider.get_secret("deepseek_api_key") == "development-secret-value"


def test_environment_secret_provider_does_not_read_unbound_environment_names() -> None:
    provider = EnvironmentSecretProvider(
        environment={
            "UNRELATED_SYSTEM_VALUE": "must-not-be-returned",
        },
        bindings={},
    )

    assert provider.get_secret("UNRELATED_SYSTEM_VALUE") is None


def test_environment_secret_provider_treats_missing_and_empty_values_as_unavailable() -> (
    None
):
    provider = EnvironmentSecretProvider(
        environment={
            "EMPTY_SECRET": "",
        },
        bindings={
            "missing_secret": "MISSING_SECRET",
            "empty_secret": "EMPTY_SECRET",
        },
    )

    assert provider.get_secret("missing_secret") is None
    assert provider.get_secret("empty_secret") is None
