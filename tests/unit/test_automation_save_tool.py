import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from asagent.automation.drafts import AutomationDraftContextStore
from asagent.core.automation import Automation, AutomationStatus, AutomationTrigger
from asagent.core.ids import AutomationId, ConversationId, UserId
from asagent.tools.automation_save import AutomationSaveTool


class _Automations:
    def __init__(self) -> None:
        self.automation: Automation | None = None
        self.trigger: AutomationTrigger | None = None

    async def get(self, automation_id: AutomationId) -> Automation | None:
        if self.automation is None or self.automation.automation_id != automation_id:
            return None
        return self.automation

    async def list_triggers(
        self, automation_id: AutomationId
    ) -> tuple[AutomationTrigger, ...]:
        if self.trigger is None or self.trigger.automation_id != automation_id:
            return ()
        return (self.trigger,)

    async def save_with_trigger(
        self, automation: Automation, trigger: AutomationTrigger
    ) -> None:
        self.automation = automation
        self.trigger = trigger

    async def save(self, automation: Automation) -> None:
        self.automation = automation


@pytest.mark.asyncio
async def test_save_tool_creates_a_draft_and_updates_the_bound_target() -> None:
    now = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    conversation_id = ConversationId("automation-draft-1")
    automations = _Automations()
    drafts = AutomationDraftContextStore()
    drafts.bind(conversation_id, None, "Australia/Perth")
    tool = AutomationSaveTool(
        automations=automations,  # type: ignore[arg-type]
        drafts=drafts,
        conversation_id=conversation_id,
        user_id=UserId("local-user"),
        now=lambda: now,
    )

    created = json.loads(
        await tool.execute(
            {
                "name": "Morning project summary",
                "plan_summary": "Summarize project changes since the previous run.",
                "schedule_kind": "daily",
                "timezone": "Australia/Perth",
                "local_time": "09:00",
            }
        )
    )

    assert created["status"] == "created"
    assert automations.automation is not None
    assert automations.automation.status is AutomationStatus.DRAFT
    assert automations.trigger is not None
    assert automations.trigger.next_run_at == datetime(2026, 8, 21, 1, 0, tzinfo=UTC)
    assert drafts.target(conversation_id) == automations.automation.automation_id
    assert drafts.timezone(conversation_id) == "Australia/Perth"
    automations.automation = replace(
        automations.automation,
        status=AutomationStatus.ACTIVE,
    )

    updated = json.loads(
        await tool.execute(
            {
                "name": "Weekday project summary",
                "plan_summary": "Summarize project changes and highlight blockers.",
                "schedule_kind": "weekly",
                "timezone": "Australia/Perth",
                "local_time": "10:00",
                "weekday": 0,
            }
        )
    )

    assert updated["status"] == "updated"
    assert updated["automation_id"] == created["automation_id"]
    assert automations.automation.name == "Weekday project summary"
    assert automations.automation.status is AutomationStatus.ACTIVE
    assert automations.trigger.weekday == 0


@pytest.mark.asyncio
async def test_update_plan_tool_updates_plan_summary_for_automation() -> None:
    from asagent.tools.automation_save import AutomationPlanUpdateTool

    now = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
    automations = _Automations()
    automations.automation = Automation(
        automation_id=AutomationId("automation-1"),
        user_id=UserId("local-user"),
        name="News digest",
        plan_summary="Navigate to broken topic link.",
        allowed_capabilities=(),
        status=AutomationStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    tool = AutomationPlanUpdateTool(
        automations=automations,  # type: ignore[arg-type]
        automation_id=AutomationId("automation-1"),
        user_id=UserId("local-user"),
        now=lambda: now,
    )

    result = json.loads(
        await tool.execute(
            {
                "refined_plan_summary": "Navigate to Google News AU homepage directly.",
                "reason": "Topic link returned 400 invalid URL, homepage is reliable.",
            }
        )
    )

    assert result["status"] == "updated"
    assert result["automation_id"] == "automation-1"
    assert (
        result["refined_plan_summary"]
        == "Navigate to Google News AU homepage directly."
    )
    assert (
        automations.automation.plan_summary
        == "Navigate to Google News AU homepage directly."
    )
