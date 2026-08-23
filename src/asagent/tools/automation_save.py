import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from asagent.automation.drafts import AutomationDraftContextStore
from asagent.core.automation import (
    Automation,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    next_run_after,
)
from asagent.core.ids import (
    AutomationId,
    AutomationTriggerId,
    ConversationId,
    UserId,
)
from asagent.core.repositories import AutomationRepository
from asagent.core.tool_definition import ToolDefinition


class AutomationSaveTool:
    def __init__(
        self,
        *,
        automations: AutomationRepository,
        drafts: AutomationDraftContextStore,
        conversation_id: ConversationId,
        user_id: UserId,
        now: Callable[[], datetime],
    ) -> None:
        self._automations = automations
        self._drafts = drafts
        self._conversation_id = conversation_id
        self._user_id = user_id
        self._now = now

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation.save_draft",
            display_name="Save automation",
            description=(
                "Save the automation discussed in this dedicated planning conversation. "
                "Call only when the task instructions and schedule are unambiguous. Ask the "
                "user a concise follow-up question instead when required information is missing. "
                "A new automation is saved as a disabled draft; an existing target is updated."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short task name."},
                    "plan_summary": {
                        "type": "string",
                        "description": "Complete instructions to execute on every run.",
                    },
                    "schedule_kind": {
                        "type": "string",
                        "enum": ["once", "daily", "weekly"],
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone such as Australia/Perth.",
                    },
                    "local_time": {
                        "type": "string",
                        "description": "Local wall-clock time in HH:MM format.",
                    },
                    "weekday": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 6,
                        "description": "Monday=0 through Sunday=6; weekly only.",
                    },
                    "run_at": {
                        "type": "string",
                        "description": "Timezone-aware ISO 8601 instant; once only.",
                    },
                },
                "required": [
                    "name",
                    "plan_summary",
                    "schedule_kind",
                    "timezone",
                    "local_time",
                ],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        name = _required_text(arguments, "name")
        plan_summary = _required_text(arguments, "plan_summary")
        kind = AutomationTriggerKind(_required_text(arguments, "schedule_kind"))
        timezone = _required_text(arguments, "timezone")
        local_time = time.fromisoformat(_required_text(arguments, "local_time"))
        weekday = _optional_int(arguments, "weekday")
        run_at = _optional_datetime(arguments, "run_at")

        target_id = self._drafts.target(self._conversation_id)
        stored = None if target_id is None else await self._automations.get(target_id)
        if target_id is not None and (
            stored is None or stored.user_id != self._user_id
        ):
            raise ValueError("automation draft target is unavailable")

        if stored is None:
            automation = Automation(
                AutomationId(f"automation_{uuid4().hex}"),
                self._user_id,
                name,
                plan_summary,
                (),
                AutomationStatus.DRAFT,
                now,
                now,
            )
            trigger_id = AutomationTriggerId(f"automation_trigger_{uuid4().hex}")
            trigger_created_at = now
            enabled = True
            operation = "created"
        else:
            automation = replace(
                stored,
                name=name,
                plan_summary=plan_summary,
                updated_at=now,
            )
            triggers = await self._automations.list_triggers(stored.automation_id)
            if len(triggers) != 1:
                raise ValueError("automation must have exactly one trigger")
            trigger_id = triggers[0].automation_trigger_id
            trigger_created_at = triggers[0].created_at
            enabled = triggers[0].enabled
            operation = "updated"

        trigger = AutomationTrigger(
            trigger_id,
            automation.automation_id,
            kind,
            timezone,
            local_time,
            weekday,
            run_at if kind is AutomationTriggerKind.ONCE else None,
            enabled,
            trigger_created_at,
            now,
        )
        if trigger.next_run_at is None:
            if kind is AutomationTriggerKind.ONCE:
                tz = ZoneInfo(timezone)
                local_now = now.astimezone(tz)
                candidate_date = local_now.date()
                candidate = datetime.combine(candidate_date, local_time, tz)
                if candidate <= local_now:
                    candidate_date += timedelta(days=1)
                    candidate = datetime.combine(candidate_date, local_time, tz)
                next_run_at = candidate.astimezone(UTC)
            else:
                calculated = next_run_after(trigger, now)
                if calculated is None:
                    raise ValueError("failed to calculate next run time")
                next_run_at = calculated
            trigger = replace(trigger, next_run_at=next_run_at)

        await self._automations.save_with_trigger(automation, trigger)
        self._drafts.bind(
            self._conversation_id,
            automation.automation_id,
            self._drafts.timezone(self._conversation_id),
        )
        assert trigger.next_run_at is not None
        return json.dumps(
            {
                "status": operation,
                "automation_id": str(automation.automation_id),
                "name": automation.name,
                "automation_status": automation.status.value,
                "next_run_at": trigger.next_run_at.astimezone(UTC).isoformat(),
            },
            separators=(",", ":"),
        )


class AutomationPlanUpdateTool:
    """Allows an automation execution to update its plan_summary after finding a working resolution."""

    def __init__(
        self,
        *,
        automations: AutomationRepository,
        automation_id: AutomationId,
        user_id: UserId,
        now: Callable[[], datetime],
    ) -> None:
        self._automations = automations
        self._automation_id = automation_id
        self._user_id = user_id
        self._now = now

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation.update_plan",
            display_name="Update task plan & instructions",
            description=(
                "Permanently update the task plan and instructions (plan_summary) for this scheduled automation. "
                "Call this when you encountered a failed step (such as an invalid URL, broken link, or changed page layout), "
                "found a working alternative, and successfully completed the task. Updating the plan ensures all future "
                "scheduled runs use the verified working URLs and steps directly."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "refined_plan_summary": {
                        "type": "string",
                        "description": "Complete, updated repeatable instructions incorporating working URLs and steps.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of what failed and how the strategy was refined.",
                    },
                },
                "required": ["refined_plan_summary"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        now = self._now()
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        refined_plan_summary = _required_text(arguments, "refined_plan_summary")
        reason = arguments.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError("reason must be a string")

        stored = await self._automations.get(self._automation_id)
        if stored is None or stored.user_id != self._user_id:
            raise ValueError("automation target is unavailable")

        updated = replace(
            stored,
            plan_summary=refined_plan_summary,
            updated_at=now,
        )
        await self._automations.save(updated)
        return json.dumps(
            {
                "status": "updated",
                "automation_id": str(updated.automation_id),
                "name": updated.name,
                "refined_plan_summary": updated.plan_summary,
                "reason": reason,
            },
            separators=(",", ":"),
        )


def _required_text(arguments: Mapping[str, object], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_int(arguments: Mapping[str, object], name: str) -> int | None:
    value = arguments.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _optional_datetime(arguments: Mapping[str, object], name: str) -> datetime | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed
