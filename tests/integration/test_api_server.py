import json
import os
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest
from fastapi import FastAPI

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.api.server import LocalApiServer
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
async def test_local_api_server_binds_loopback_dynamic_port_and_serves_health() -> None:
    server = LocalApiServer(_create_app(), port=0)
    ready = await server.start()

    try:
        assert ready.host == "127.0.0.1"
        assert ready.port > 0
        assert ready.pid == os.getpid()
        assert json.loads(ready.to_json()) == {
            "host": "127.0.0.1",
            "pid": os.getpid(),
            "port": ready.port,
            "protocol_version": 1,
        }

        async with httpx.AsyncClient(
            base_url=f"http://{ready.host}:{ready.port}",
        ) as client:
            response = await client.get(
                "/api/v1/health",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        await server.close()


@pytest.mark.parametrize(
    ("host", "port", "message"),
    [
        ("0.0.0.0", 0, "host must be 127.0.0.1"),
        ("127.0.0.1", -1, "port must be between 0 and 65535"),
        ("127.0.0.1", 65536, "port must be between 0 and 65535"),
        ("127.0.0.1", True, "port must be an integer"),
    ],
)
def test_local_api_server_rejects_unsafe_or_invalid_binding(
    host: str,
    port: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LocalApiServer(_create_app(), host=host, port=port)
