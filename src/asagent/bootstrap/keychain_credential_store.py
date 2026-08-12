import sys
from typing import Protocol, cast

from asagent.core.ids import ConnectionId

_SERVICE_NAME = "asagent.connection-credentials"


class CredentialStoreError(RuntimeError):
    """A system credential store operation failed without exposing its secret."""


class CredentialStoreUnavailableError(CredentialStoreError):
    """The current operating system has no supported credential store adapter."""


class _KeyringClient(Protocol):
    def get_password(
        self,
        service_name: str,
        username: str,
    ) -> str | None: ...

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None: ...

    def delete_password(
        self,
        service_name: str,
        username: str,
    ) -> None: ...


class MacOSKeychainCredentialStore:
    """CredentialStore backed by the current macOS user's Keychain."""

    def __init__(
        self,
        *,
        keyring_client: _KeyringClient | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._platform_name = platform_name or sys.platform
        self._keyring = keyring_client or _load_keyring()

    def get_credential(self, connection_id: ConnectionId) -> str | None:
        self._require_macos()

        try:
            return self._keyring.get_password(
                _SERVICE_NAME,
                str(connection_id),
            )
        except Exception as error:
            raise CredentialStoreError(
                "could not read the system credential store",
            ) from error

    def save_credential(
        self,
        connection_id: ConnectionId,
        credential: str,
    ) -> None:
        self._require_macos()

        if not credential:
            raise ValueError("credentials must not be empty")

        try:
            self._keyring.set_password(
                _SERVICE_NAME,
                str(connection_id),
                credential,
            )
        except Exception as error:
            raise CredentialStoreError(
                "could not save to the system credential store",
            ) from error

    def delete_credential(self, connection_id: ConnectionId) -> None:
        self._require_macos()

        if self.get_credential(connection_id) is None:
            return

        try:
            self._keyring.delete_password(
                _SERVICE_NAME,
                str(connection_id),
            )
        except Exception as error:
            raise CredentialStoreError(
                "could not delete from the system credential store",
            ) from error

    def _require_macos(self) -> None:
        if self._platform_name != "darwin":
            raise CredentialStoreUnavailableError(
                "macOS Keychain credential storage is unavailable on this platform",
            )


def _load_keyring() -> _KeyringClient:
    try:
        import keyring
    except ImportError as error:
        raise CredentialStoreUnavailableError(
            "the system credential store dependency is unavailable",
        ) from error

    return cast(_KeyringClient, keyring)
