from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.file_change import FileChange, FileChangeOperation, FileChangeStatus
from asagent.core.ids import FileChangeId, RunId
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import file_changes


class SqliteFileChangeRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(self, file_change_id: FileChangeId) -> FileChange | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(file_changes).where(
                    file_changes.c.file_change_id == str(file_change_id)
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else _to_file_change(dict(row))

    async def list_for_run(self, run_id: RunId) -> tuple[FileChange, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(file_changes)
                .where(file_changes.c.run_id == str(run_id))
                .order_by(
                    file_changes.c.created_at.asc(), file_changes.c.file_change_id.asc()
                )
            )
            rows = result.mappings().all()
        return tuple(_to_file_change(dict(row)) for row in rows)

    async def save(self, file_change: FileChange) -> None:
        values = _values(file_change)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(file_changes)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[file_changes.c.file_change_id], set_=values
                )
            )


def _values(change: FileChange) -> dict[str, object]:
    return {
        "file_change_id": str(change.file_change_id),
        "run_id": str(change.run_id),
        "operation": change.operation.value,
        "status": change.status.value,
        "root_path": change.root_path,
        "relative_path": change.relative_path,
        "before_hash": change.before_hash,
        "after_hash": change.after_hash,
        "snapshot_ref": change.snapshot_ref,
        "created_at": _to_utc(change.created_at),
        "updated_at": _to_utc(change.updated_at),
    }


def _to_file_change(row: Mapping[str, object]) -> FileChange:
    operation = FileChangeOperation(_string(row, "operation"))
    status = FileChangeStatus(_string(row, "status"))
    return FileChange(
        FileChangeId(_string(row, "file_change_id")),
        RunId(_string(row, "run_id")),
        operation,
        status,
        _string(row, "root_path"),
        _string(row, "relative_path"),
        _optional_string(row, "before_hash"),
        _optional_string(row, "after_hash"),
        _optional_string(row, "snapshot_ref"),
        _datetime(row, "created_at"),
        _datetime(row, "updated_at"),
    )


def _string(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _optional_string(row: Mapping[str, object], field: str) -> str | None:
    value = row[field]
    if value is not None and not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string or null")
    return value


def _datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
