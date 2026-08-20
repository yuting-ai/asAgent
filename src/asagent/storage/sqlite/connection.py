from pathlib import Path
from typing import Protocol, cast

from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

_BUSY_TIMEOUT_MS = 5_000


class _Cursor(Protocol):
    def close(self) -> None: ...

    def execute(self, operation: str) -> object: ...


class _SqliteDbApiConnection(Protocol):
    def cursor(self) -> _Cursor: ...


def create_sqlite_async_engine(database_path: Path) -> AsyncEngine:
    if isinstance(database_path, AsyncEngine):
        raise TypeError(
            "database_path must be a Path or str, not an AsyncEngine instance"
        )

    database_url = URL.create(
        "sqlite+aiosqlite",
        database=str(database_path),
    )
    engine = create_async_engine(database_url)

    event.listen(engine.sync_engine, "connect", _configure_connection)

    return engine


def _configure_connection(
    dbapi_connection: object,
    _connection_record: ConnectionPoolEntry,
) -> None:
    connection = cast(_SqliteDbApiConnection, dbapi_connection)
    cursor = connection.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.execute("PRAGMA synchronous = FULL")
    finally:
        cursor.close()
