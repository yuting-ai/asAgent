from datetime import UTC, datetime, time
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from asagent.core.automation import (
    Automation,
    AutomationExecutionStatus,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
)
from asagent.core.ids import AutomationId, AutomationTriggerId, UserId
from asagent.core.repositories import AutomationRepository
from asagent.storage.sqlite.automation_repository import SqliteAutomationRepository


def _upgrade(path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{path}")
    command.upgrade(config, "head")


def _automation(
    now: datetime, status: AutomationStatus = AutomationStatus.ACTIVE
) -> Automation:
    return Automation(
        AutomationId("automation-1"),
        UserId("local-user"),
        "Morning report",
        "Read the report and summarize material changes.",
        ("mcp.reports.read",),
        status,
        now,
        now,
    )


def _daily_trigger(now: datetime, next_run_at: datetime) -> AutomationTrigger:
    return AutomationTrigger(
        AutomationTriggerId("trigger-1"),
        AutomationId("automation-1"),
        AutomationTriggerKind.DAILY,
        "Australia/Perth",
        time(9),
        None,
        next_run_at,
        True,
        now,
        now,
    )


@pytest.mark.asyncio
async def test_persists_automations_and_claims_each_due_trigger_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    created_at = datetime(2026, 8, 20, 0, tzinfo=UTC)
    due_at = datetime(2026, 8, 20, 1, tzinfo=UTC)
    now = datetime(2026, 8, 20, 1, 5, tzinfo=UTC)
    repository = SqliteAutomationRepository(database_path)
    protocol: AutomationRepository = repository
    try:
        assert isinstance(protocol, AutomationRepository)
        await repository.save_with_trigger(
            _automation(created_at), _daily_trigger(created_at, due_at)
        )

        claimed = await repository.claim_due(now)

        assert len(claimed) == 1
        assert claimed[0].scheduled_for == due_at
        assert claimed[0].status is AutomationExecutionStatus.CLAIMED
        assert await repository.claim_due(now) == ()
        assert await repository.list_executions(AutomationId("automation-1")) == claimed
        trigger = await repository.get_trigger(AutomationTriggerId("trigger-1"))
        assert trigger is not None
        assert trigger.next_run_at == datetime(2026, 8, 21, 1, tzinfo=UTC)
        assert await repository.delete(AutomationId("automation-1")) is True
        assert await repository.get(AutomationId("automation-1")) is None
        assert await repository.list_triggers(AutomationId("automation-1")) == ()
        assert await repository.list_executions(AutomationId("automation-1")) == ()
    finally:
        await repository.aclose()


@pytest.mark.asyncio
async def test_missed_recurring_trigger_skips_to_the_next_future_occurrence(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    created_at = datetime(2026, 8, 20, 0, tzinfo=UTC)
    due_at = datetime(2026, 8, 18, 1, tzinfo=UTC)
    now = datetime(2026, 8, 20, 1, 5, tzinfo=UTC)
    repository = SqliteAutomationRepository(database_path)
    try:
        await repository.save(_automation(created_at))
        await repository.save_trigger(_daily_trigger(created_at, due_at))

        executions = await repository.claim_due(now, missed_before=now)

        assert [execution.status for execution in executions] == [
            AutomationExecutionStatus.MISSED
        ]
        trigger = await repository.get_trigger(AutomationTriggerId("trigger-1"))
        assert trigger is not None
        assert trigger.next_run_at == datetime(2026, 8, 21, 1, tzinfo=UTC)
    finally:
        await repository.aclose()


@pytest.mark.asyncio
async def test_paused_automations_are_not_claimed(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)
    now = datetime(2026, 8, 20, 1, tzinfo=UTC)
    repository = SqliteAutomationRepository(database_path)
    try:
        await repository.save(_automation(now, AutomationStatus.PAUSED))
        await repository.save_trigger(_daily_trigger(now, now))

        assert await repository.claim_due(now) == ()
    finally:
        await repository.aclose()
