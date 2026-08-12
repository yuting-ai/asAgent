from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from asagent.core.ids import ConnectionId, UserId


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    REAUTHENTICATION_REQUIRED = "reauthentication_required"


@dataclass(frozen=True, slots=True)
class Connection:
    """Non-sensitive metadata for one external account connection."""

    connection_id: ConnectionId
    user_id: UserId
    service_id: str
    account_label: str
    granted_scopes: frozenset[str]
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime


@runtime_checkable
class CredentialStore(Protocol):
    """Stores an opaque credential outside SQLite and ordinary configuration."""

    def get_credential(self, connection_id: ConnectionId) -> str | None: ...

    def save_credential(
        self,
        connection_id: ConnectionId,
        credential: str,
    ) -> None: ...

    def delete_credential(self, connection_id: ConnectionId) -> None: ...
