from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from asagent.core.ids import (
    AutomationExecutionId,
    AutomationId,
    AutomationTriggerId,
    RunId,
    UserId,
)


class AutomationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"


class AutomationTriggerKind(StrEnum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class AutomationExecutionStatus(StrEnum):
    CLAIMED = "claimed"
    MISSED = "missed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Automation:
    automation_id: AutomationId
    user_id: UserId
    name: str
    plan_summary: str
    allowed_capabilities: tuple[str, ...]
    status: AutomationStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if not self.plan_summary.strip():
            raise ValueError("plan_summary must not be blank")
        if any(not capability.strip() for capability in self.allowed_capabilities):
            raise ValueError("allowed_capabilities must not contain blank values")
        if len(set(self.allowed_capabilities)) != len(self.allowed_capabilities):
            raise ValueError("allowed_capabilities must not contain duplicates")


@dataclass(frozen=True, slots=True)
class AutomationTrigger:
    automation_trigger_id: AutomationTriggerId
    automation_id: AutomationId
    kind: AutomationTriggerKind
    timezone: str
    local_time: time
    weekday: int | None
    next_run_at: datetime | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        if self.kind is AutomationTriggerKind.WEEKLY:
            if self.weekday is None or not 0 <= self.weekday <= 6:
                raise ValueError("weekly triggers require weekday from 0 through 6")
        elif self.weekday is not None:
            raise ValueError("only weekly triggers can have a weekday")
        if self.next_run_at is not None and self.next_run_at.tzinfo is None:
            raise ValueError("next_run_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AutomationExecution:
    automation_execution_id: AutomationExecutionId
    automation_id: AutomationId
    automation_trigger_id: AutomationTriggerId
    scheduled_for: datetime
    status: AutomationExecutionStatus
    claimed_at: datetime
    run_id: RunId | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.scheduled_for.tzinfo is None:
            raise ValueError("scheduled_for must be timezone-aware")
        if self.claimed_at.tzinfo is None:
            raise ValueError("claimed_at must be timezone-aware")
        if self.completed_at is not None and self.completed_at.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware")
        if self.status in {
            AutomationExecutionStatus.CLAIMED,
            AutomationExecutionStatus.MISSED,
        }:
            if self.completed_at is not None:
                raise ValueError("unfinished executions cannot have completed_at")
        elif self.completed_at is None:
            raise ValueError("finished executions require completed_at")
        elif (
            self.status is not AutomationExecutionStatus.FAILED and self.run_id is None
        ):
            raise ValueError("non-failed finished executions require run_id")


def next_run_after(trigger: AutomationTrigger, after: datetime) -> datetime | None:
    """Return the next scheduled UTC instant strictly after ``after``."""
    if trigger.kind is AutomationTriggerKind.ONCE:
        return None
    if after.tzinfo is None:
        raise ValueError("after must be timezone-aware")

    timezone = ZoneInfo(trigger.timezone)
    local_after = after.astimezone(timezone)
    candidate_date = local_after.date()
    if trigger.kind is AutomationTriggerKind.WEEKLY:
        assert trigger.weekday is not None
        candidate_date += timedelta(
            days=(trigger.weekday - candidate_date.weekday()) % 7
        )

    candidate = datetime.combine(candidate_date, trigger.local_time, timezone)
    if candidate <= local_after:
        candidate_date += timedelta(
            days=7 if trigger.kind is AutomationTriggerKind.WEEKLY else 1
        )
        candidate = datetime.combine(candidate_date, trigger.local_time, timezone)
    return candidate.astimezone(UTC)
