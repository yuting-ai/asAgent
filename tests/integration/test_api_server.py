import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.api.server import LocalApiServer
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, EventId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository

_UNUSED_RUNS = cast(RunRepository, object())

_TOKEN = LocalApiToken("test-token")


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


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


async def _read_sse_event(lines: object) -> tuple[str, str, str]:
    iterator = cast(AsyncIterator[str], lines)
    first = await anext(iterator)
    second = await anext(iterator)
    third = await anext(iterator)
    assert await anext(iterator) == ""
    return first, second, third


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


@pytest.mark.asyncio
async def test_local_api_server_runs_application_lifespan() -> None:
    events: list[str] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        events.append("startup")
        try:
            yield
        finally:
            events.append("shutdown")

    app = FastAPI(lifespan=lifespan)
    server = LocalApiServer(app, port=0)
    await server.start()

    assert events == ["startup"]

    await server.close()

    assert events == ["startup", "shutdown"]


@pytest.mark.asyncio
async def test_local_api_server_streams_live_run_events_over_tcp(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    completed_at = datetime(2026, 8, 11, 12, 0, 1, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    app = create_app(
        access_token=_TOKEN,
        conversations=conversations,
        runs=runs,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=UnusedRunStarter(),
            now=lambda: created_at,
            new_run_id=lambda: RunId("unused-run"),
            new_message_id=lambda: MessageId("unused-message"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    server = LocalApiServer(app, port=0)

    try:
        await conversations.save(
            Conversation(
                conversation_id=ConversationId("conv-local"),
                user_id=UserId("local-user"),
                created_at=created_at,
                updated_at=created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-live"),
                conversation_id=ConversationId("conv-local"),
                status=RunStatus.CALLING_MODEL,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        ready = await server.start()

        async with httpx.AsyncClient(
            base_url=f"http://{ready.host}:{ready.port}",
            timeout=httpx.Timeout(5.0),
        ) as client:
            async with client.stream(
                "GET",
                "/api/v1/runs/run-live/events",
                headers={"Authorization": "Bearer test-token"},
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith(
                    "text/event-stream",
                )
                lines = response.aiter_lines()

                await runs.append_event(
                    RunEvent(
                        event_id=EventId("event-1"),
                        run_id=RunId("run-live"),
                        conversation_id=ConversationId("conv-local"),
                        sequence=1,
                        event_type="run.started",
                        created_at=created_at,
                        data={},
                    ),
                )
                first = await _read_sse_event(lines)
                assert first == (
                    "id: 1",
                    "event: run.started",
                    'data: {"conversation_id":"conv-local","created_at":"2026-08-11T12:00:00Z","data":{},"event_id":"event-1","event_type":"run.started","run_id":"run-live","sequence":1}',
                )

                await runs.append_event(
                    RunEvent(
                        event_id=EventId("event-2"),
                        run_id=RunId("run-live"),
                        conversation_id=ConversationId("conv-local"),
                        sequence=2,
                        event_type="run.completed",
                        created_at=completed_at,
                        data={"steps_used": 1},
                    ),
                )
                await runs.save(
                    Run(
                        run_id=RunId("run-live"),
                        conversation_id=ConversationId("conv-local"),
                        status=RunStatus.COMPLETED,
                        created_at=created_at,
                        updated_at=completed_at,
                    ),
                )
                second = await _read_sse_event(lines)
                assert second == (
                    "id: 2",
                    "event: run.completed",
                    'data: {"conversation_id":"conv-local","created_at":"2026-08-11T12:00:01Z","data":{"steps_used":1},"event_id":"event-2","event_type":"run.completed","run_id":"run-live","sequence":2}',
                )

                with pytest.raises(StopAsyncIteration):
                    await anext(lines)
    finally:
        await server.close()
        await runs.aclose()
        await conversations.aclose()


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
