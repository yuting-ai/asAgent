from collections.abc import Mapping

from asagent.core.connection import CredentialStore
from asagent.core.ids import ConnectionId


class CredentialStoreSecretProvider:
    """Adapts explicitly bound Keychain credentials to model secret references."""

    def __init__(
        self,
        *,
        credential_store: CredentialStore,
        bindings: Mapping[str, ConnectionId],
    ) -> None:
        self._credential_store = credential_store
        self._bindings = bindings

    def get_secret(self, secret_id: str) -> str | None:
        connection_id = self._bindings.get(secret_id)
        if connection_id is None:
            return None

        return self._credential_store.get_credential(connection_id)
