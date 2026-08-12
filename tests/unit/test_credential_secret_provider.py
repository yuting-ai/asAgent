from asagent.bootstrap.credential_secret_provider import CredentialStoreSecretProvider
from asagent.core.ids import ConnectionId


class FakeCredentialStore:
    def __init__(self) -> None:
        self.credentials = {ConnectionId("connection-model"): "model-key"}

    def get_credential(self, connection_id: ConnectionId) -> str | None:
        return self.credentials.get(connection_id)

    def save_credential(self, connection_id: ConnectionId, credential: str) -> None:
        self.credentials[connection_id] = credential

    def delete_credential(self, connection_id: ConnectionId) -> None:
        self.credentials.pop(connection_id, None)


def test_looks_up_only_explicitly_bound_secret_ids() -> None:
    provider = CredentialStoreSecretProvider(
        credential_store=FakeCredentialStore(),
        bindings={"model-key": ConnectionId("connection-model")},
    )

    assert provider.get_secret("model-key") == "model-key"
    assert provider.get_secret("unbound-key") is None
