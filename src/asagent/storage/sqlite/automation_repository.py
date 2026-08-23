import json
from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import cast
from uuid import uuid4

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from asagent.core.automation import (
    Automation,
    AutomationExecution,
    AutomationExecutionStatus,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    next_run_after,
)
from asagent.core.ids import (
    AutomationExecutionId,
    AutomationId,
    AutomationTriggerId,
    RunId,
    UserId,
)
from asagent.storage.sqlite.connection import create_sqlite_async_engine
from asagent.storage.sqlite.schema import (
    automation_executions,
    automation_triggers,
    automations,
    users,
)


class SqliteAutomationRepository:
    def __init__(self, database_path: Path) -> None:
        self._engine = create_sqlite_async_engine(database_path)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def get(self, automation_id: AutomationId) -> Automation | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automations).where(
                    automations.c.automation_id == str(automation_id)
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else _to_automation(dict(row))

    async def list_for_user(self, user_id: UserId) -> tuple[Automation, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automations)
                .where(automations.c.user_id == str(user_id))
                .order_by(
                    automations.c.updated_at.desc(), automations.c.automation_id.desc()
                )
            )
            rows = result.mappings().all()
        return tuple(_to_automation(dict(row)) for row in rows)

    async def save(self, automation: Automation) -> None:
        values = _automation_values(automation)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(users)
                .values(
                    user_id=str(automation.user_id),
                    created_at=_to_utc(automation.created_at),
                )
                .on_conflict_do_nothing(index_elements=[users.c.user_id])
            )
            await connection.execute(
                sqlite_insert(automations)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[automations.c.automation_id], set_=values
                )
            )

    async def save_with_trigger(
        self, automation: Automation, trigger: AutomationTrigger
    ) -> None:
        automation_values = _automation_values(automation)
        trigger_values = _trigger_values(trigger)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(users)
                .values(
                    user_id=str(automation.user_id),
                    created_at=_to_utc(automation.created_at),
                )
                .on_conflict_do_nothing(index_elements=[users.c.user_id])
            )
            await connection.execute(
                sqlite_insert(automations)
                .values(**automation_values)
                .on_conflict_do_update(
                    index_elements=[automations.c.automation_id], set_=automation_values
                )
            )
            await connection.execute(
                sqlite_insert(automation_triggers)
                .values(**trigger_values)
                .on_conflict_do_update(
                    index_elements=[automation_triggers.c.automation_trigger_id],
                    set_=trigger_values,
                )
            )

    async def delete(self, automation_id: AutomationId) -> bool:
        async with self._engine.begin() as connection:
            await connection.execute(
                automation_executions.delete().where(
                    automation_executions.c.automation_id == str(automation_id)
                )
            )
            await connection.execute(
                automation_triggers.delete().where(
                    automation_triggers.c.automation_id == str(automation_id)
                )
            )
            result = await connection.execute(
                automations.delete().where(
                    automations.c.automation_id == str(automation_id)
                )
            )
        return bool(result.rowcount)

    async def get_trigger(
        self, automation_trigger_id: AutomationTriggerId
    ) -> AutomationTrigger | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automation_triggers).where(
                    automation_triggers.c.automation_trigger_id
                    == str(automation_trigger_id)
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else _to_trigger(dict(row))

    async def list_triggers(
        self, automation_id: AutomationId
    ) -> tuple[AutomationTrigger, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automation_triggers)
                .where(automation_triggers.c.automation_id == str(automation_id))
                .order_by(
                    automation_triggers.c.next_run_at.asc(),
                    automation_triggers.c.automation_trigger_id.asc(),
                )
            )
            rows = result.mappings().all()
        return tuple(_to_trigger(dict(row)) for row in rows)

    async def save_trigger(self, trigger: AutomationTrigger) -> None:
        values = _trigger_values(trigger)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(automation_triggers)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[automation_triggers.c.automation_trigger_id],
                    set_=values,
                )
            )

    async def claim_due(
        self,
        now: datetime,
        *,
        missed_before: datetime | None = None,
        limit: int = 100,
    ) -> tuple[AutomationExecution, ...]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if missed_before is not None and missed_before.tzinfo is None:
            raise ValueError("missed_before must be timezone-aware")
        if limit < 1:
            raise ValueError("limit must be positive")

        now_utc = _to_utc(now)
        missed_before_utc = None if missed_before is None else _to_utc(missed_before)
        claimed: list[AutomationExecution] = []
        async with self._engine.begin() as connection:
            result = await connection.execute(
                select(automation_triggers)
                .join(
                    automations,
                    automation_triggers.c.automation_id == automations.c.automation_id,
                )
                .where(
                    and_(
                        automations.c.status == AutomationStatus.ACTIVE.value,
                        automation_triggers.c.enabled == 1,
                        automation_triggers.c.next_run_at.is_not(None),
                        automation_triggers.c.next_run_at <= now_utc,
                    )
                )
                .order_by(
                    automation_triggers.c.next_run_at.asc(),
                    automation_triggers.c.automation_trigger_id.asc(),
                )
                .limit(limit)
            )
            rows = result.mappings().all()

            for row in rows:
                trigger = _to_trigger(dict(row))
                assert trigger.next_run_at is not None
                scheduled_for = trigger.next_run_at
                is_missed = (
                    missed_before_utc is not None and scheduled_for < missed_before_utc
                ) or (scheduled_for < now_utc - timedelta(hours=1))
                next_at = (
                    next_run_after(trigger, now_utc)
                    if is_missed
                    else next_run_after(trigger, scheduled_for)
                )
                update_result = await connection.execute(
                    update(automation_triggers)
                    .where(
                        automation_triggers.c.automation_trigger_id
                        == str(trigger.automation_trigger_id),
                        automation_triggers.c.next_run_at == scheduled_for,
                    )
                    .values(next_run_at=next_at, updated_at=now_utc)
                )
                if not update_result.rowcount:
                    continue

                execution = AutomationExecution(
                    AutomationExecutionId(f"automation_execution_{uuid4().hex}"),
                    trigger.automation_id,
                    trigger.automation_trigger_id,
                    scheduled_for,
                    (
                        AutomationExecutionStatus.MISSED
                        if is_missed
                        else AutomationExecutionStatus.CLAIMED
                    ),
                    now_utc,
                )
                await connection.execute(
                    sqlite_insert(automation_executions).values(
                        **_execution_values(execution)
                    )
                )
                claimed.append(execution)
        return tuple(claimed)

    async def get_execution(
        self, automation_execution_id: AutomationExecutionId
    ) -> AutomationExecution | None:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automation_executions).where(
                    automation_executions.c.automation_execution_id
                    == str(automation_execution_id)
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else _to_execution(dict(row))

    async def list_executions(
        self, automation_id: AutomationId
    ) -> tuple[AutomationExecution, ...]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                select(automation_executions)
                .where(automation_executions.c.automation_id == str(automation_id))
                .order_by(
                    automation_executions.c.scheduled_for.desc(),
                    automation_executions.c.automation_execution_id.desc(),
                )
            )
            rows = result.mappings().all()
        return tuple(_to_execution(dict(row)) for row in rows)

    async def save_execution(self, execution: AutomationExecution) -> None:
        values = _execution_values(execution)
        async with self._engine.begin() as connection:
            await connection.execute(
                sqlite_insert(automation_executions)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[automation_executions.c.automation_execution_id],
                    set_=values,
                )
            )


def _automation_values(automation: Automation) -> dict[str, object]:
    return {
        "automation_id": str(automation.automation_id),
        "user_id": str(automation.user_id),
        "name": automation.name,
        "plan_summary": automation.plan_summary,
        "allowed_capabilities_json": json.dumps(
            automation.allowed_capabilities, ensure_ascii=False, separators=(",", ":")
        ),
        "status": automation.status.value,
        "created_at": _to_utc(automation.created_at),
        "updated_at": _to_utc(automation.updated_at),
    }


def _trigger_values(trigger: AutomationTrigger) -> dict[str, object]:
    return {
        "automation_trigger_id": str(trigger.automation_trigger_id),
        "automation_id": str(trigger.automation_id),
        "kind": trigger.kind.value,
        "timezone": trigger.timezone,
        "local_time": trigger.local_time.isoformat(),
        "weekday": trigger.weekday,
        "next_run_at": (
            None if trigger.next_run_at is None else _to_utc(trigger.next_run_at)
        ),
        "enabled": int(trigger.enabled),
        "created_at": _to_utc(trigger.created_at),
        "updated_at": _to_utc(trigger.updated_at),
    }


def _execution_values(execution: AutomationExecution) -> dict[str, object]:
    return {
        "automation_execution_id": str(execution.automation_execution_id),
        "automation_id": str(execution.automation_id),
        "automation_trigger_id": str(execution.automation_trigger_id),
        "scheduled_for": _to_utc(execution.scheduled_for),
        "status": execution.status.value,
        "claimed_at": _to_utc(execution.claimed_at),
        "run_id": None if execution.run_id is None else str(execution.run_id),
        "completed_at": (
            None if execution.completed_at is None else _to_utc(execution.completed_at)
        ),
    }


def _to_automation(row: Mapping[str, object]) -> Automation:
    return Automation(
        AutomationId(_required_str(row, "automation_id")),
        UserId(_required_str(row, "user_id")),
        _required_str(row, "name"),
        _required_str(row, "plan_summary"),
        _capabilities(_required_str(row, "allowed_capabilities_json")),
        AutomationStatus(_required_str(row, "status")),
        _required_datetime(row, "created_at"),
        _required_datetime(row, "updated_at"),
    )


def _to_trigger(row: Mapping[str, object]) -> AutomationTrigger:
    weekday = row["weekday"]
    if weekday is not None and (
        not isinstance(weekday, int) or isinstance(weekday, bool)
    ):
        raise RuntimeError("persisted weekday must be an integer or null")
    next_run_at = row["next_run_at"]
    if next_run_at is not None and not isinstance(next_run_at, datetime):
        raise RuntimeError("persisted next_run_at must be a datetime or null")
    return AutomationTrigger(
        AutomationTriggerId(_required_str(row, "automation_trigger_id")),
        AutomationId(_required_str(row, "automation_id")),
        AutomationTriggerKind(_required_str(row, "kind")),
        _required_str(row, "timezone"),
        time.fromisoformat(_required_str(row, "local_time")),
        weekday,
        None if next_run_at is None else _to_utc(next_run_at),
        _required_bool(row, "enabled"),
        _required_datetime(row, "created_at"),
        _required_datetime(row, "updated_at"),
    )


def _to_execution(row: Mapping[str, object]) -> AutomationExecution:
    return AutomationExecution(
        AutomationExecutionId(_required_str(row, "automation_execution_id")),
        AutomationId(_required_str(row, "automation_id")),
        AutomationTriggerId(_required_str(row, "automation_trigger_id")),
        _required_datetime(row, "scheduled_for"),
        AutomationExecutionStatus(_required_str(row, "status")),
        _required_datetime(row, "claimed_at"),
        _optional_run_id(row, "run_id"),
        _optional_datetime(row, "completed_at"),
    )


def _capabilities(value: str) -> tuple[str, ...]:
    parsed: object = json.loads(value)
    if not isinstance(parsed, list) or any(
        not isinstance(capability, str) for capability in parsed
    ):
        raise RuntimeError("persisted allowed capabilities must be strings")
    return tuple(cast(list[str], parsed))


def _required_str(row: Mapping[str, object], field: str) -> str:
    value = row[field]
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string")
    return value


def _required_bool(row: Mapping[str, object], field: str) -> bool:
    value = row[field]
    if value not in (0, 1, False, True):
        raise RuntimeError(f"persisted {field} must be a boolean")
    return bool(value)


def _required_datetime(row: Mapping[str, object], field: str) -> datetime:
    value = row[field]
    if not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime")
    return _to_utc(value)


def _optional_datetime(row: Mapping[str, object], field: str) -> datetime | None:
    value = row[field]
    if value is not None and not isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} must be a datetime or null")
    return None if value is None else _to_utc(value)


def _optional_run_id(row: Mapping[str, object], field: str) -> RunId | None:
    value = row[field]
    if value is not None and not isinstance(value, str):
        raise RuntimeError(f"persisted {field} must be a string or null")
    return None if value is None else RunId(value)


def _to_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
