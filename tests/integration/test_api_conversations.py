from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
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


@pytest.mark.asyncio
async def test_list_conversation_messages_returns_visible_messages_in_sequence_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation = _conversation(
        ConversationId("conv-local"),
        UserId("local-user"),
        datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
    )
    user_message = UserMessage(
        message_id=MessageId("msg-user"),
        conversation_id=conversation.conversation_id,
        content="Hello, asAgent.",
        created_at=datetime(2026, 8, 11, 8, 1, tzinfo=UTC),
    )
    assistant_message = AssistantMessage(
        message_id=MessageId("msg-assistant"),
        conversation_id=conversation.conversation_id,
        content="Hello! How can I help?",
        created_at=datetime(2026, 8, 11, 8, 2, tzinfo=UTC),
    )

    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await repository.save(conversation)
        await repository.append_message(user_message)
        await repository.append_message(assistant_message)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/conversations/conv-local/messages",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await repository.aclose()

    assert response.status_code == 200

    payload = response.json()
    assert [item["message_id"] for item in payload] == [
        "msg-user",
        "msg-assistant",
    ]
    assert [item["role"] for item in payload] == ["user", "assistant"]
    assert [item["content"] for item in payload] == [
        "Hello, asAgent.",
        "Hello! How can I help?",
    ]
    assert [datetime.fromisoformat(item["created_at"]) for item in payload] == [
        user_message.created_at,
        assistant_message.created_at,
    ]
    assert all("conversation_id" not in item for item in payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conversation_id",
    (
        "missing",
        "conv-other-user",
    ),
)
async def test_list_conversation_messages_hides_unknown_or_other_user_conversations(
    tmp_path: Path,
    conversation_id: str,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    other_user_conversation = _conversation(
        ConversationId("conv-other-user"),
        UserId("other-user"),
        datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
    )

    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await repository.save(other_user_conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await repository.aclose()

    assert response.status_code == 404
    assert response.json() == {"detail": "conversation not found"}


@pytest.mark.asyncio
async def test_list_conversation_messages_requires_the_current_local_api_token(
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
            response = await client.get(
                "/api/v1/conversations/conv-local/messages",
            )
    finally:
        await repository.aclose()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid local API credentials"}


@pytest.mark.asyncio
async def test_create_conversation_persists_an_empty_local_conversation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversation_id = ConversationId("conv-created")
    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
        conversation_id_factory=lambda: conversation_id,
        clock=lambda: created_at,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/conversations",
                headers={"Authorization": "Bearer test-token"},
                json={},
            )

        stored = await repository.get(conversation_id)
        messages = await repository.list_messages(conversation_id)
    finally:
        await repository.aclose()

    assert response.status_code == 201
    assert response.json() == {
        "conversation_id": "conv-created",
        "created_at": "2026-08-11T12:00:00Z",
        "updated_at": "2026-08-11T12:00:00Z",
    }
    assert stored == _conversation(
        conversation_id,
        UserId("local-user"),
        created_at,
        created_at,
    )
    assert messages == ()


@pytest.mark.asyncio
async def test_create_conversation_rejects_unknown_request_fields(
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
            response = await client.post(
                "/api/v1/conversations",
                headers={"Authorization": "Bearer test-token"},
                json={"title": "not supported yet"},
            )

        stored = await repository.list_for_user(UserId("local-user"))
    finally:
        await repository.aclose()

    assert response.status_code == 422
    assert stored == ()


@pytest.mark.asyncio
async def test_create_conversation_requires_the_current_local_api_token(
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
            response = await client.post("/api/v1/conversations", json={})

        stored = await repository.list_for_user(UserId("local-user"))
    finally:
        await repository.aclose()

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid local API credentials"}
    assert stored == ()
