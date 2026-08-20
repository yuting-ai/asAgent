from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from fastapi import FastAPI

from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.bootstrap.storage_settings import StorageSettingsStore
from asagent.core.conversation import Conversation
from asagent.core.ids import FileChangeId, MessageId, RunId
from asagent.core.messages import UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
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


def _app(tmp_path: Path) -> FastAPI:
    conversations = InMemoryConversationRepository()
    storage_store = StorageSettingsStore(tmp_path / "config")
    snapshots = FileChangeSnapshotStore(tmp_path / "data")
    return create_app(
        access_token=_TOKEN,
        conversations=conversations,
        runs=_UNUSED_RUNS,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=UnusedRunStarter(),
            now=lambda: datetime(2026, 8, 20, tzinfo=UTC),
            new_run_id=lambda: RunId("unused-run"),
            new_message_id=lambda: MessageId("unused-message"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
        storage_settings=storage_store,
        file_change_snapshots=snapshots,
    )


@pytest.mark.asyncio
async def test_get_and_update_storage_settings(tmp_path: Path) -> None:
    app = _app(tmp_path)
    snapshots = FileChangeSnapshotStore(tmp_path / "data")
    snapshots.save(FileChangeId("c1"), b"test snapshot")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET default settings
        response = await client.get(
            "/api/v1/settings/storage",
            headers={"Authorization": f"Bearer {_TOKEN.value}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["snapshot_retention_days"] == 7
        assert data["usage_bytes"] == len(b"test snapshot")
        assert data["snapshot_count"] == 1

        # PUT update settings
        update_res = await client.put(
            "/api/v1/settings/storage",
            headers={"Authorization": f"Bearer {_TOKEN.value}"},
            json={"snapshot_retention_days": 3},
        )
        assert update_res.status_code == 200
        assert update_res.json()["snapshot_retention_days"] == 3

        # Clear snapshots
        clear_res = await client.post(
            "/api/v1/settings/storage/clear",
            headers={"Authorization": f"Bearer {_TOKEN.value}"},
        )
        assert clear_res.status_code == 200
        assert clear_res.json()["freed_bytes"] == len(b"test snapshot")
        assert clear_res.json()["deleted_count"] == 1

        # Verify usage is now 0
        get_res_after = await client.get(
            "/api/v1/settings/storage",
            headers={"Authorization": f"Bearer {_TOKEN.value}"},
        )
        assert get_res_after.status_code == 200
        assert get_res_after.json()["usage_bytes"] == 0
        assert get_res_after.json()["snapshot_count"] == 0
