from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.bootstrap.agent_settings import AgentSettings, AgentSettingsStore
from asagent.core.conversation import Conversation
from asagent.core.ids import MessageId, RunId
from asagent.core.messages import UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

_TOKEN = LocalApiToken("test-token")
_UNUSED_RUNS = cast(RunRepository, object())


class UnusedRunStarter:
    async def start(
        self,
        *,
        conversation: Conversation,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        del conversation, user_message, run
        raise AssertionError("run submission is not used by this test")


def _discard_submission(submission: SubmittedRun) -> None:
    del submission


def _cancel_nothing(run_id: RunId) -> bool:
    del run_id
    return False


def _app(tmp_path: Path):
    conversations = InMemoryConversationRepository()
    return create_app(
        access_token=_TOKEN,
        conversations=conversations,
        runs=_UNUSED_RUNS,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=UnusedRunStarter(),
            now=lambda: datetime(2026, 8, 16, tzinfo=UTC),
            new_run_id=lambda: RunId("unused-run"),
            new_message_id=lambda: MessageId("unused-message"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
        agent_settings=AgentSettingsStore(tmp_path / "config"),
    )


@pytest.mark.asyncio
async def test_agent_settings_default_and_update(tmp_path: Path) -> None:
    transport = httpx.ASGITransport(app=_app(tmp_path))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        missing = await client.get("/api/v1/agent-settings")
        assert missing.status_code == 401

        read = await client.get(
            "/api/v1/agent-settings",
            headers={"Authorization": "Bearer test-token"},
        )
        assert read.status_code == 200
        assert read.json() == {"max_steps": 20}

        saved = await client.put(
            "/api/v1/agent-settings",
            headers={"Authorization": "Bearer test-token"},
            json={"max_steps": 30},
        )
        assert saved.status_code == 200
        assert saved.json() == {"max_steps": 30}

        reread = await client.get(
            "/api/v1/agent-settings",
            headers={"Authorization": "Bearer test-token"},
        )
        assert reread.json() == {"max_steps": 30}

    assert AgentSettingsStore(tmp_path / "config").get() == AgentSettings(max_steps=30)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"max_steps": 0},
        {"max_steps": -1},
        {"max_steps": 51},
        {"max_steps": 1.5},
        {"max_steps": 1.0},
        {"max_steps": True},
        {"max_steps": 20, "extra": True},
        {},
    ],
)
async def test_agent_settings_rejects_invalid_payloads(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    transport = httpx.ASGITransport(app=_app(tmp_path))
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.put(
            "/api/v1/agent-settings",
            headers={"Authorization": "Bearer test-token"},
            json=payload,
        )
    assert response.status_code == 422
