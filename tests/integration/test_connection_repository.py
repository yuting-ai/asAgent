from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.connection import Connection, ConnectionStatus
from asagent.core.ids import ConnectionId, UserId
from asagent.core.repositories import ConnectionRepository
from asagent.storage.sqlite.connection_repository import (
    SqliteConnectionRepository,
)


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _connection(
    connection_id: ConnectionId,
    *,
    user_id: UserId | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    status: ConnectionStatus = ConnectionStatus.ACTIVE,
) -> Connection:
    creation_time = created_at or datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    owner_id = user_id if user_id is not None else UserId("local-user")

    return Connection(
        connection_id=connection_id,
        user_id=owner_id,
        service_id="gmail",
        account_label="Primary Gmail account",
        granted_scopes=frozenset(
            {"https://www.googleapis.com/auth/gmail.readonly"},
        ),
        status=status,
        created_at=creation_time,
        updated_at=updated_at or creation_time,
    )


@pytest.mark.asyncio
async def test_persists_connections_across_repository_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    connection = _connection(ConnectionId("connection-1"))
    repository = SqliteConnectionRepository(database_path)
    protocol: ConnectionRepository = repository

    assert isinstance(protocol, ConnectionRepository)

    try:
        await repository.save(connection)
    finally:
        await repository.aclose()

    reopened = SqliteConnectionRepository(database_path)
    try:
        assert await reopened.get(connection.connection_id) == connection
        assert await reopened.get(ConnectionId("missing")) is None
        assert await reopened.list_for_user(UserId("local-user")) == (connection,)
    finally:
        await reopened.aclose()


@pytest.mark.asyncio
async def test_save_replaces_connection_and_orders_by_recent_activity(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    repository = SqliteConnectionRepository(database_path)
    older = _connection(ConnectionId("connection-older"))
    newer = _connection(
        ConnectionId("connection-newer"),
        updated_at=datetime(2026, 8, 12, 12, 1, tzinfo=UTC),
    )
    updated = _connection(
        older.connection_id,
        updated_at=datetime(2026, 8, 12, 12, 2, tzinfo=UTC),
        status=ConnectionStatus.REAUTHENTICATION_REQUIRED,
    )

    try:
        await repository.save(older)
        await repository.save(newer)
        await repository.save(updated)

        assert await repository.get(updated.connection_id) == updated
        assert await repository.list_for_user(UserId("local-user")) == (
            updated,
            newer,
        )
    finally:
        await repository.aclose()


@pytest.mark.asyncio
async def test_deletes_connection_metadata_and_normalizes_datetimes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    local_time = datetime(
        2026,
        8,
        12,
        20,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    connection = _connection(
        ConnectionId("connection-1"),
        created_at=local_time,
    )
    repository = SqliteConnectionRepository(database_path)

    try:
        await repository.save(connection)

        stored = await repository.get(connection.connection_id)
        assert stored is not None
        assert stored.created_at == datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

        assert await repository.delete(connection.connection_id) is True
        assert await repository.delete(connection.connection_id) is False
        assert await repository.get(connection.connection_id) is None
    finally:
        await repository.aclose()
