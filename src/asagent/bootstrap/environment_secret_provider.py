from collections.abc import Mapping


class EnvironmentSecretProvider:
    """Development-only SecretProvider backed by an explicit environment mapping."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str],
        bindings: Mapping[str, str],
    ) -> None:
        self._environment = environment
        self._bindings = bindings

    def get_secret(self, secret_id: str) -> str | None:
        environment_name = self._bindings.get(secret_id)
        if environment_name is None:
            return None

        value = self._environment.get(environment_name)
        if not value:
            return None

        return value
