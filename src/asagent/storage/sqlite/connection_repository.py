import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.connection import Connection, ConnectionStatus
from asagent.core.ids import ConnectionId, UserId
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import connections, users


class SqliteConnectionRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(self, connection_id: ConnectionId) -> Connection | None:
        async with self._engine.connect() as database_connection:
            result = await database_connection.execute(
                select(connections).where(
                    connections.c.connection_id == str(connection_id),
                ),
            )
            row = result.mappings().one_or_none()

        if row is None:
            return None

        return _to_connection(dict(row))

    async def list_for_user(self, user_id: UserId) -> tuple[Connection, ...]:
        async with self._engine.connect() as database_connection:
            result = await database_connection.execute(
                select(connections)
                .where(connections.c.user_id == str(user_id))
                .order_by(
                    connections.c.updated_at.desc(),
                    connections.c.connection_id.desc(),
                ),
            )
            rows = result.mappings().all()

        return tuple(_to_connection(dict(row)) for row in rows)

    async def save(self, connection: Connection) -> None:
        async with self._engine.begin() as database_connection:
            await database_connection.execute(
                sqlite_insert(users)
                .values(
                    user_id=str(connection.user_id),
                    created_at=_to_utc(connection.created_at),
                )
                .on_conflict_do_nothing(index_elements=[users.c.user_id]),
            )
            await database_connection.execute(
                sqlite_insert(connections)
                .values(
                    connection_id=str(connection.connection_id),
                    user_id=str(connection.user_id),
                    service_id=connection.service_id,
                    account_label=connection.account_label,
                    granted_scopes_json=_serialize_scopes(
                        connection.granted_scopes,
                    ),
                    status=connection.status.value,
                    created_at=_to_utc(connection.created_at),
                    updated_at=_to_utc(connection.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[connections.c.connection_id],
                    set_={
                        "user_id": str(connection.user_id),
                        "service_id": connection.service_id,
                        "account_label": connection.account_label,
                        "granted_scopes_json": _serialize_scopes(
                            connection.granted_scopes,
                        ),
                        "status": connection.status.value,
                        "created_at": _to_utc(connection.created_at),
                        "updated_at": _to_utc(connection.updated_at),
                    },
                ),
            )

    async def delete(self, connection_id: ConnectionId) -> bool:
        async with self._engine.begin() as database_connection:
            result = await database_connection.execute(
                connections.delete().where(
                    connections.c.connection_id == str(connection_id),
                ),
            )

        return bool(result.rowcount)


def _to_connection(row: Mapping[str, object]) -> Connection:
    status_value = _required_str(row, "status")

    try:
        status = ConnectionStatus(status_value)
    except ValueError as error:
        raise RuntimeError(
            f"unknown persisted connection status: {status_value}",
        ) from error

    return Connection(
        connection_id=ConnectionId(_required_str(row, "connection_id")),
        user_id=UserId(_required_str(row, "user_id")),
        service_id=_required_str(row, "service_id"),
        account_label=_required_str(row, "account_label"),
        granted_scopes=_deserialize_scopes(
            _required_str(row, "granted_scopes_json"),
        ),
        status=status,
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _serialize_scopes(scopes: frozenset[str]) -> str:
    return json.dumps(
        sorted(scopes),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _deserialize_scopes(serialized: str) -> frozenset[str]:
    value: object = json.loads(serialized)
    if not isinstance(value, list) or any(
        not isinstance(scope, str) or not scope for scope in value
    ):
        raise RuntimeError("persisted connection scopes must be strings")

    return frozenset(cast(list[str], value))


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _required_datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
