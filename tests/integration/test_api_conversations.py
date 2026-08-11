from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, UserId
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
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
async def test_list_conversations_returns_only_local_user_metadata(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    first = _conversation(
        ConversationId("conv-first"),
        UserId("local-user"),
        datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 8, 1, tzinfo=UTC),
    )
    second = _conversation(
        ConversationId("conv-second"),
        UserId("local-user"),
        datetime(2026, 8, 11, 9, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 9, 1, tzinfo=UTC),
    )
    other_user = _conversation(
        ConversationId("conv-other"),
        UserId("other-user"),
        datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 10, 1, tzinfo=UTC),
    )

    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await repository.save(first)
        await repository.save(second)
        await repository.save(other_user)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/conversations",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await repository.aclose()

    assert response.status_code == 200

    payload = response.json()
    assert [item["conversation_id"] for item in payload] == [
        "conv-first",
        "conv-second",
    ]
    assert [datetime.fromisoformat(item["created_at"]) for item in payload] == [
        first.created_at,
        second.created_at,
    ]
    assert [datetime.fromisoformat(item["updated_at"]) for item in payload] == [
        first.updated_at,
        second.updated_at,
    ]
    assert all("user_id" not in item for item in payload)
    assert all("messages" not in item for item in payload)


@pytest.mark.asyncio
async def test_list_conversations_requires_the_current_local_api_token(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/conversations")
    finally:
        await repository.aclose()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid local API credentials"}
