from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository


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
    conversations: SqliteConversationRepository,
) -> RunSubmissionService:
    return RunSubmissionService(
        conversations=conversations,
        run_starter=UnusedRunStarter(),
        now=lambda: datetime(2026, 8, 11, tzinfo=UTC),
        new_run_id=lambda: RunId("unused-run"),
        new_message_id=lambda: MessageId("unused-message"),
    )


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


def _conversation(
    conversation_id: ConversationId,
    user_id: UserId,
    created_at: datetime,
    updated_at: datetime,
) -> Conversation:
    return Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        created_at=created_at,
        updated_at=updated_at,
    )


@pytest.mark.asyncio
async def test_get_run_returns_completed_run_for_local_user(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 11, 12, 5, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            _conversation(
                ConversationId("conv-local"),
                UserId("local-user"),
                created_at,
                created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-completed"),
                conversation_id=ConversationId("conv-local"),
                status=RunStatus.COMPLETED,
                created_at=created_at,
                updated_at=updated_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/runs/run-completed",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-completed",
        "status": "completed",
        "created_at": "2026-08-11T12:00:00Z",
        "updated_at": "2026-08-11T12:05:00Z",
    }


@pytest.mark.asyncio
async def test_get_run_returns_not_found_for_missing_or_other_user_runs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            _conversation(
                ConversationId("conv-other"),
                UserId("other-user"),
                created_at,
                created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-other"),
                conversation_id=ConversationId("conv-other"),
                status=RunStatus.COMPLETED,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            missing = await client.get(
                "/api/v1/runs/run-missing",
                headers={"Authorization": "Bearer test-token"},
            )
            other_user = await client.get(
                "/api/v1/runs/run-other",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert missing.status_code == 404
    assert missing.json() == {"detail": "run not found"}
    assert other_user.status_code == 404
    assert other_user.json() == {"detail": "run not found"}


@pytest.mark.asyncio
async def test_get_run_requires_bearer_token(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            missing = await client.get("/api/v1/runs/run-any")
            wrong = await client.get(
                "/api/v1/runs/run-any",
                headers={"Authorization": "Bearer wrong-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert missing.status_code == 401
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_cancel_run_requests_cooperative_cancellation_for_active_local_run(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    cancelled: list[RunId] = []

    def cancel_run(run_id: RunId) -> bool:
        cancelled.append(run_id)
        return True

    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=cancel_run,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            _conversation(
                ConversationId("conv-local"),
                UserId("local-user"),
                created_at,
                created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-local"),
                conversation_id=ConversationId("conv-local"),
                status=RunStatus.CALLING_MODEL,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/runs/run-local/cancel",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert cancelled == [RunId("run-local")]
    assert response.status_code == 202
    assert response.json() == {
        "run_id": "run-local",
        "cancellation_requested": True,
    }


@pytest.mark.asyncio
async def test_cancel_run_returns_not_found_for_missing_or_other_user_runs(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    cancelled: list[RunId] = []

    def cancel_run(run_id: RunId) -> bool:
        cancelled.append(run_id)
        return True

    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=cancel_run,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            _conversation(
                ConversationId("conv-other"),
                UserId("other-user"),
                created_at,
                created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-other"),
                conversation_id=ConversationId("conv-other"),
                status=RunStatus.CALLING_MODEL,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            missing = await client.post(
                "/api/v1/runs/run-missing/cancel",
                headers={"Authorization": "Bearer test-token"},
            )
            other_user = await client.post(
                "/api/v1/runs/run-other/cancel",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert cancelled == []
    assert missing.status_code == 404
    assert missing.json() == {"detail": "run not found"}
    assert other_user.status_code == 404
    assert other_user.json() == {"detail": "run not found"}


@pytest.mark.asyncio
async def test_cancel_run_returns_conflict_when_run_is_not_active(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=_unused_run_submission(conversations),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            _conversation(
                ConversationId("conv-local"),
                UserId("local-user"),
                created_at,
                created_at,
            ),
        )
        await runs.save(
            Run(
                run_id=RunId("run-local"),
                conversation_id=ConversationId("conv-local"),
                status=RunStatus.COMPLETED,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/runs/run-local/cancel",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 409
    assert response.json() == {"detail": "run is not active"}
