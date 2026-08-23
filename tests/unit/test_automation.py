from datetime import UTC, datetime, time

import pytest

from asagent.core.automation import (
    Automation,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    next_run_after,
)
from asagent.core.ids import AutomationId, AutomationTriggerId, UserId


def test_automation_rejects_blank_or_duplicate_configuration() -> None:
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)

    with pytest.raises(ValueError, match="name must not be blank"):
        Automation(
            AutomationId("automation-1"),
            UserId("local-user"),
            " ",
            "Check a report",
            (),
            AutomationStatus.DRAFT,
            now,
            now,
        )

    with pytest.raises(ValueError, match="must not contain duplicates"):
        Automation(
            AutomationId("automation-1"),
            UserId("local-user"),
            "Report check",
            "Check a report",
            ("mcp.report", "mcp.report"),
            AutomationStatus.DRAFT,
            now,
            now,
        )


def test_trigger_requires_a_valid_timezone_and_weekly_day() -> None:
    now = datetime(2026, 8, 20, 12, tzinfo=UTC)

    with pytest.raises(ValueError, match="IANA timezone"):
        AutomationTrigger(
            AutomationTriggerId("trigger-1"),
            AutomationId("automation-1"),
            AutomationTriggerKind.DAILY,
            "not/a-timezone",
            time(9),
            None,
            now,
            True,
            now,
            now,
        )

    with pytest.raises(ValueError, match="require weekday"):
        AutomationTrigger(
            AutomationTriggerId("trigger-1"),
            AutomationId("automation-1"),
            AutomationTriggerKind.WEEKLY,
            "Australia/Perth",
            time(9),
            None,
            now,
            True,
            now,
            now,
        )


def test_next_run_after_uses_the_trigger_local_timezone() -> None:
    now = datetime(2026, 8, 20, 1, 30, tzinfo=UTC)
    daily = AutomationTrigger(
        AutomationTriggerId("daily"),
        AutomationId("automation-1"),
        AutomationTriggerKind.DAILY,
        "Australia/Perth",
        time(9),
        None,
        now,
        True,
        now,
        now,
    )
    weekly = AutomationTrigger(
        AutomationTriggerId("weekly"),
        AutomationId("automation-1"),
        AutomationTriggerKind.WEEKLY,
        "Australia/Perth",
        time(9),
        0,
        now,
        True,
        now,
        now,
    )

    assert next_run_after(daily, now) == datetime(2026, 8, 21, 1, tzinfo=UTC)
    assert next_run_after(weekly, now) == datetime(2026, 8, 24, 1, tzinfo=UTC)
