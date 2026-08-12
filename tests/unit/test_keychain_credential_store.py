import pytest

from asagent.bootstrap.keychain_credential_store import (
    CredentialStoreUnavailableError,
    MacOSKeychainCredentialStore,
)
from asagent.core.connection import CredentialStore
from asagent.core.ids import ConnectionId


class FakeKeyringClient:
    def __init__(self) -> None:
        self.passwords: dict[tuple[str, str], str] = {}

    def get_password(
        self,
        service_name: str,
        username: str,
    ) -> str | None:
        return self.passwords.get((service_name, username))

    def set_password(
        self,
        service_name: str,
        username: str,
        password: str,
    ) -> None:
        self.passwords[(service_name, username)] = password

    def delete_password(
        self,
        service_name: str,
        username: str,
    ) -> None:
        del self.passwords[(service_name, username)]


def test_macos_keychain_store_satisfies_protocol_and_is_connection_scoped() -> None:
    store: CredentialStore = MacOSKeychainCredentialStore(
        keyring_client=FakeKeyringClient(),
        platform_name="darwin",
    )
    primary_connection = ConnectionId("connection-primary")
    secondary_connection = ConnectionId("connection-secondary")

    store.save_credential(primary_connection, "secret-primary")

    assert store.get_credential(primary_connection) == "secret-primary"
    assert store.get_credential(secondary_connection) is None

    store.delete_credential(primary_connection)

    assert store.get_credential(primary_connection) is None


def test_macos_keychain_store_rejects_empty_credentials() -> None:
    store = MacOSKeychainCredentialStore(
        keyring_client=FakeKeyringClient(),
        platform_name="darwin",
    )

    with pytest.raises(ValueError, match="must not be empty"):
        store.save_credential(ConnectionId("connection-1"), "")


def test_macos_keychain_store_fails_clearly_on_other_platforms() -> None:
    store = MacOSKeychainCredentialStore(
        keyring_client=FakeKeyringClient(),
        platform_name="win32",
    )

    with pytest.raises(CredentialStoreUnavailableError, match="unavailable"):
        store.get_credential(ConnectionId("connection-1"))
