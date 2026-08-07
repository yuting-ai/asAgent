from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """Returns a secret by reference without exposing its storage mechanism."""

    def get_secret(self, secret_id: str) -> str | None:
        """Return None when the requested secret does not exist."""
