import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.ids import ConversationId, EventId, RunId, ToolCallId
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call import ToolCall
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import run_events, runs, tool_calls


class SqliteRunRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(self, run_id: RunId) -> Run | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(runs).where(runs.c.run_id == str(run_id)),
            )
            row = result.mappings().one_or_none()

        if row is None:
            return None

        return _to_run(dict(row))

    async def list_for_conversation(
        self,
        conversation_id: ConversationId,
    ) -> tuple[Run, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(runs)
                .where(runs.c.conversation_id == str(conversation_id))
                .order_by(runs.c.created_at.asc(), runs.c.run_id.asc()),
            )
            rows = result.mappings().all()

        return tuple(_to_run(dict(row)) for row in rows)

    async def save(self, run: Run) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(runs)
                .values(
                    run_id=str(run.run_id),
                    conversation_id=str(run.conversation_id),
                    status=run.status.value,
                    created_at=_to_utc(run.created_at),
                    updated_at=_to_utc(run.updated_at),
                )
                .on_conflict_do_update(
                    index_elements=[runs.c.run_id],
                    set_={
                        "conversation_id": str(run.conversation_id),
                        "status": run.status.value,
                        "created_at": _to_utc(run.created_at),
                        "updated_at": _to_utc(run.updated_at),
                    },
                ),
            )

    async def append_event(self, event: RunEvent) -> None:
        async with self._engine.begin() as connection:
            persisted_conversation_id = await connection.scalar(
                select(runs.c.conversation_id).where(
                    runs.c.run_id == str(event.run_id),
                ),
            )
            if persisted_conversation_id is None:
                raise ValueError("cannot append an event to an unknown run")
            if persisted_conversation_id != str(event.conversation_id):
                raise ValueError(
                    "event conversation_id does not match the persisted run",
                )

            await connection.execute(
                run_events.insert().values(
                    event_id=str(event.event_id),
                    run_id=str(event.run_id),
                    sequence=event.sequence,
                    event_type=event.event_type,
                    created_at=_to_utc(event.created_at),
                    data_json=_serialize_json_object(event.data),
                ),
            )

    async def list_events(
        self,
        run_id: RunId,
        *,
        after_sequence: int = 0,
    ) -> tuple[RunEvent, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(
                    run_events,
                    runs.c.conversation_id,
                )
                .join(runs, run_events.c.run_id == runs.c.run_id)
                .where(
                    run_events.c.run_id == str(run_id),
                    run_events.c.sequence > after_sequence,
                )
                .order_by(run_events.c.sequence.asc()),
            )
            rows = result.mappings().all()

        return tuple(_to_run_event(dict(row)) for row in rows)

    async def save_tool_call(self, tool_call: ToolCall) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(tool_calls)
                .values(
                    tool_call_id=str(tool_call.tool_call_id),
                    run_id=str(tool_call.run_id),
                    model_call_id=tool_call.model_call_id,
                    tool_id=tool_call.tool_id,
                    arguments_json=_serialize_json_object(tool_call.arguments),
                    result=tool_call.result,
                    error=tool_call.error,
                    created_at=_to_utc(tool_call.created_at),
                    completed_at=_optional_utc(tool_call.completed_at),
                )
                .on_conflict_do_update(
                    index_elements=[tool_calls.c.tool_call_id],
                    set_={
                        "run_id": str(tool_call.run_id),
                        "model_call_id": tool_call.model_call_id,
                        "tool_id": tool_call.tool_id,
                        "arguments_json": _serialize_json_object(
                            tool_call.arguments,
                        ),
                        "result": tool_call.result,
                        "error": tool_call.error,
                        "created_at": _to_utc(tool_call.created_at),
                        "completed_at": _optional_utc(tool_call.completed_at),
                    },
                ),
            )

    async def list_tool_calls(
        self,
        run_id: RunId,
    ) -> tuple[ToolCall, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(tool_calls)
                .where(tool_calls.c.run_id == str(run_id))
                .order_by(
                    tool_calls.c.created_at.asc(),
                    tool_calls.c.tool_call_id.asc(),
                ),
            )
            rows = result.mappings().all()

        return tuple(_to_tool_call(dict(row)) for row in rows)


def _to_run(row: Mapping[str, object]) -> Run:
    status_value = _required_str(row, "status")

    try:
        status = RunStatus(status_value)
    except ValueError as error:
        raise RuntimeError(f"unknown persisted run status: {status_value}") from error

    return Run(
        run_id=RunId(_required_str(row, "run_id")),
        conversation_id=ConversationId(_required_str(row, "conversation_id")),
        status=status,
        created_at=_required_datetime(row, "created_at"),
        updated_at=_required_datetime(row, "updated_at"),
    )


def _to_run_event(row: Mapping[str, object]) -> RunEvent:
    return RunEvent(
        event_id=EventId(_required_str(row, "event_id")),
        run_id=RunId(_required_str(row, "run_id")),
        conversation_id=ConversationId(_required_str(row, "conversation_id")),
        sequence=_required_int(row, "sequence"),
        event_type=_required_str(row, "event_type"),
        created_at=_required_datetime(row, "created_at"),
        data=_deserialize_json_object(_required_str(row, "data_json")),
    )


def _to_tool_call(row: Mapping[str, object]) -> ToolCall:
    completed_at = row["completed_at"]
    if completed_at is not None and not isinstance(completed_at, datetime):
        raise RuntimeError("persisted completed_at must be a datetime or null")

    return ToolCall(
        tool_call_id=ToolCallId(_required_str(row, "tool_call_id")),
        run_id=RunId(_required_str(row, "run_id")),
        model_call_id=_required_str(row, "model_call_id"),
        tool_id=_required_str(row, "tool_id"),
        arguments=_deserialize_json_object(
            _required_str(row, "arguments_json"),
        ),
        result=_optional_str(row, "result"),
        error=_optional_str(row, "error"),
        created_at=_required_datetime(row, "created_at"),
        completed_at=_optional_utc(completed_at),
    )


def _serialize_json_object(value: Mapping[str, object]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_json_object(serialized: str) -> dict[str, object]:
    value: object = json.loads(serialized)
    if not isinstance(value, dict):
        raise RuntimeError("persisted JSON value must be an object")
    if any(not isinstance(key, str) for key in value):
        raise RuntimeError("persisted JSON object keys must be strings")

    return cast(dict[str, object], value)


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _optional_str(
    row: Mapping[str, object],
    field: str,
) -> str | None:
    value = row[field]
    if value is not None and not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string or null")
    return value


def _required_int(row: Mapping[str, object], field: str) -> int:
    value = row[field]
    if not isinstance(value, int):
        raise RuntimeError(f"persisted {field} must be an integer")
    return value


def _required_datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _optional_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _to_utc(value)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
