import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.run_dispatcher import InProcessRunDispatcher
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.cli import build_persistent_development_runtime
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter


def _upgrade(database_path: Path) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{database_path}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_submit_message_dispatches_background_execution(tmp_path: Path) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation_id = ConversationId("conversation-1")
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    finisher = SqliteRunFinisher(database_path)
    runtime = build_persistent_development_runtime(
        conversations=conversations,
        runs=runs,
        starter=starter,
        finisher=finisher,
    )
    execution_finished = asyncio.Event()
    run_submission = RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=lambda: created_at,
        new_run_id=lambda: RunId("run-1"),
        new_message_id=lambda: MessageId("message-1"),
    )

    async def execute_submitted(
        submission: SubmittedRun,
        cancellation_token: RunCancellationToken,
    ) -> None:
        try:
            await runtime.execute_submitted(
                submission=submission,
                model_name="development-tools",
                system_prompt="Use tools.",
                cancellation_token=cancellation_token,
            )
        finally:
            execution_finished.set()

    dispatcher = InProcessRunDispatcher(execute_submitted=execute_submitted)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=run_submission,
        dispatch_submitted_run=dispatcher.dispatch,
        cancel_run=dispatcher.cancel,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(
            Conversation(
                conversation_id=conversation_id,
                user_id=UserId("local-user"),
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers={"Authorization": "Bearer test-token"},
                json={"content": "Hello"},
            )

        assert response.status_code == 201
        assert response.json()["run"]["status"] == "created"
        assert response.json()["run"]["run_id"] == "run-1"

        async with asyncio.timeout(5.0):
            await execution_finished.wait()

        assert tuple(
            message.content
            for message in await conversations.list_messages(conversation_id)
        ) == (
            "Hello",
            "Tool result: Echo: Hello",
        )
        stored_run = await runs.get(RunId("run-1"))
        assert stored_run is not None
        assert stored_run.status is RunStatus.COMPLETED
    finally:
        await dispatcher.aclose()
        await finisher.aclose()
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()
