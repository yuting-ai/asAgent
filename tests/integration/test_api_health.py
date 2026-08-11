from datetime import UTC, datetime
from typing import cast

import httpx
import pytest
from fastapi import FastAPI

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.ids import MessageId, RunId
from asagent.core.messages import UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

_UNUSED_RUNS = cast(RunRepository, object())

_TOKEN = LocalApiToken("test-token")


class UnusedRunStarter:
    async def start(
        self,
        *,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        del user_message, run
        raise AssertionError("run submission is not used by this test")


def _discard_submission(submission: SubmittedRun) -> None:
    del submission


def _cancel_nothing(run_id: RunId) -> bool:
    del run_id
    return False


def _unused_run_submission(
    conversations: InMemoryConversationRepository,
) -> RunSubmissionService:
    return RunSubmissionService(
        conversations=conversations,
        run_starter=UnusedRunStarter(),
        now=lambda: datetime(2026, 8, 11, tzinfo=UTC),
        new_run_id=lambda: RunId("unused-run"),
        new_message_id=lambda: MessageId("unused-message"),
    )


def _create_app() -> FastAPI:
    conversations = InMemoryConversationRepository()
    return create_app(
        access_token=_TOKEN,
        conversations=conversations,
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )


@pytest.mark.asyncio
async def test_health_endpoint_accepts_the_current_local_api_token() -> None:
    app = _create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"Authorization": "Basic test-token"},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "Bearer test token"},
    ),
)
async def test_health_endpoint_rejects_invalid_local_api_credentials(
    headers: dict[str, str],
) -> None:
    app = _create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid local API credentials"}
    assert response.headers["www-authenticate"] == "Bearer"
