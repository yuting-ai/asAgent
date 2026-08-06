from ragent.models.secrets import SecretProvider


class InMemorySecretProvider:
    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = secrets

    def get_secret(self, secret_id: str) -> str | None:
        return self._secrets.get(secret_id)


def test_secret_provider_is_structural_and_handles_missing_secrets() -> None:
    provider: SecretProvider = InMemorySecretProvider(
        {"example_key": "value-from-secret-store"}
    )

    assert isinstance(provider, SecretProvider)
    assert provider.get_secret("example_key") == "value-from-secret-store"
    assert provider.get_secret("missing_key") is None
