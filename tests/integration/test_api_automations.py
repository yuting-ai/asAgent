from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.automation.drafts import AutomationDraftContextStore
from asagent.core.automation import Automation, AutomationStatus, AutomationTrigger
from asagent.core.conversation import Conversation
from asagent.core.ids import AutomationId, ConversationId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.repositories import AutomationRepository, RunRepository
from asagent.core.run import Run
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.tools.browser_run_bindings import BrowserRunBindings


class _Automations:
    def __init__(self) -> None:
        now = datetime(2026, 8, 20, tzinfo=UTC)
        self.value = Automation(
            AutomationId("automation-1"),
            UserId("local-user"),
            "Report",
            "Read it.",
            (),
            AutomationStatus.ACTIVE,
            now,
            now,
        )
        self.trigger: AutomationTrigger | None = None

    async def get(self, automation_id: AutomationId) -> Automation | None:
        return self.value if automation_id == self.value.automation_id else None

    async def list_for_user(self, user_id: UserId) -> tuple[Automation, ...]:
        return (self.value,) if user_id == self.value.user_id else ()

    async def save(self, automation: Automation) -> None:
        self.value = automation

    async def save_with_trigger(
        self, automation: Automation, trigger: AutomationTrigger
    ) -> None:
        self.value = automation
        self.trigger = trigger

    async def delete(self, automation_id: AutomationId) -> bool:
        return automation_id == self.value.automation_id

    async def list_triggers(
        self, automation_id: AutomationId
    ) -> tuple[AutomationTrigger, ...]:
        if automation_id != self.value.automation_id or self.trigger is None:
            return ()
        return (self.trigger,)

    async def get_execution(self, automation_execution_id: object) -> None:
        del automation_execution_id
        return None

    async def list_executions(self, automation_id: AutomationId) -> tuple[object, ...]:
        del automation_id
        return ()


class _Starter:
    def __init__(self, conversations: InMemoryConversationRepository) -> None:
        self._conversations = conversations

    async def start(
        self, *, conversation: Conversation, user_message: UserMessage, run: Run
    ) -> None:
        del run
        await self._conversations.save(conversation)
        await self._conversations.append_message(user_message)


def _discard(submission: SubmittedRun) -> None:
    del submission


@pytest.mark.asyncio
async def test_automation_routes_are_authenticated_and_update_status() -> None:
    conversations = InMemoryConversationRepository()
    automations = _Automations()
    automation_drafts = AutomationDraftContextStore()
    browser_run_bindings = BrowserRunBindings()
    execution_conversation = Conversation(
        ConversationId("automation-execution-conversation"),
        UserId("local-user"),
        datetime(2026, 8, 20, tzinfo=UTC),
        datetime(2026, 8, 20, tzinfo=UTC),
        kind="automation_execution",
    )
    await conversations.save(execution_conversation)
    app = create_app(
        access_token=LocalApiToken("token"),
        conversations=conversations,
        runs=cast(RunRepository, object()),
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=_Starter(conversations),
            now=lambda: datetime(2026, 8, 20, tzinfo=UTC),
            new_run_id=lambda: RunId("run"),
            new_message_id=lambda: MessageId("message"),
        ),
        dispatch_submitted_run=_discard,
        cancel_run=lambda _: False,
        automations=cast(AutomationRepository, automations),
        automation_drafts=automation_drafts,
        browser_run_bindings=browser_run_bindings,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/api/v1/automations")).status_code == 401
        assert (
            await client.get(
                "/api/v1/automations", headers={"Authorization": "Bearer token"}
            )
        ).json()[0]["status"] == "active"
        visible_conversations = await client.get(
            "/api/v1/conversations",
            headers={"Authorization": "Bearer token"},
        )
        changed = await client.put(
            "/api/v1/automations/automation-1/status",
            headers={"Authorization": "Bearer token"},
            json={"status": "paused"},
        )
        created = await client.post(
            "/api/v1/automations",
            headers={"Authorization": "Bearer token"},
            json={
                "name": "Weekly report",
                "plan_summary": "Read the weekly report.",
                "allowed_capabilities": ["mcp.reports.read"],
                "trigger": {
                    "kind": "weekly",
                    "timezone": "Australia/Perth",
                    "local_time": "09:00",
                    "weekday": 0,
                    "next_run_at": "2026-08-24T01:00:00Z",
                },
            },
        )
        created_id = created.json()["automation_id"]
        updated = await client.put(
            f"/api/v1/automations/{created_id}",
            headers={"Authorization": "Bearer token"},
            json={
                "name": "Updated weekly report",
                "plan_summary": "Read the changed weekly report.",
                "allowed_capabilities": [],
                "trigger": {
                    "kind": "daily",
                    "timezone": "Australia/Perth",
                    "local_time": "10:00",
                },
            },
        )
        draft = await client.post(
            "/api/v1/automation-drafts",
            headers={"Authorization": "Bearer token"},
            json={
                "automation_id": created_id,
                "timezone": "Australia/Perth",
            },
        )
        draft_id = ConversationId(draft.json()["conversation_id"])
        assert automation_drafts.target(draft_id) == AutomationId(created_id)
        assert automation_drafts.timezone(draft_id) == "Australia/Perth"
        submitted_draft = await client.post(
            f"/api/v1/automation-drafts/{draft_id}/messages",
            headers={"Authorization": "Bearer token"},
            json={
                "content": "Run this every morning at nine.",
                "tab_id": "automation-browser-tab",
            },
        )
        submitted_follow_up = await client.post(
            f"/api/v1/automation-drafts/{draft_id}/messages",
            headers={"Authorization": "Bearer token"},
            json={"content": "Make that eight instead."},
        )
        draft_messages = await client.get(
            f"/api/v1/automation-drafts/{draft_id}/messages",
            headers={"Authorization": "Bearer token"},
        )
        deleted_draft = await client.delete(
            f"/api/v1/automation-drafts/{draft_id}",
            headers={"Authorization": "Bearer token"},
        )
        deleted = await client.delete(
            f"/api/v1/automations/{created_id}",
            headers={"Authorization": "Bearer token"},
        )
    assert changed.status_code == 200
    assert visible_conversations.status_code == 200
    assert visible_conversations.json() == []
    assert changed.json()["status"] == "paused"
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated weekly report"
    assert deleted.status_code == 204
    assert draft.status_code == 201
    assert submitted_draft.status_code == 201, submitted_draft.text
    assert submitted_follow_up.status_code == 201, submitted_follow_up.text
    assert [message["content"] for message in draft_messages.json()] == [
        "Run this every morning at nine.",
        "Make that eight instead.",
    ]
    assert (
        browser_run_bindings.take(RunId(submitted_draft.json()["run"]["run_id"]))
        == "automation-browser-tab"
    )
    assert deleted_draft.status_code == 204
    assert not automation_drafts.contains(draft_id)
