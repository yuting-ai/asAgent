from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import httpx
import pytest
from alembic.config import Config

from alembic import command
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import RunRepository
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter

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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        "conv-second",
        "conv-first",
    ]
    assert [datetime.fromisoformat(item["created_at"]) for item in payload] == [
        second.created_at,
        first.created_at,
    ]
    assert [datetime.fromisoformat(item["updated_at"]) for item in payload] == [
        second.updated_at,
        first.updated_at,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        "title": None,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
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


@pytest.mark.asyncio
async def test_update_conversation_title_persists_for_local_user(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv-local"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        title="Original title",
    )
    repository = SqliteConversationRepository(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=repository,
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
        clock=lambda: datetime(2026, 8, 11, 13, 0, tzinfo=UTC),
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await repository.save(conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.patch(
                "/api/v1/conversations/conv-local",
                headers={"Authorization": "Bearer test-token"},
                json={"title": "  Renamed conversation  "},
            )

        stored = await repository.get(conversation.conversation_id)
    finally:
        await repository.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "conv-local",
        "created_at": "2026-08-11T08:00:00Z",
        "updated_at": "2026-08-11T08:00:00Z",
        "title": "Renamed conversation",
    }
    assert stored is not None
    assert stored.title == "Renamed conversation"
    assert stored.updated_at == created_at


@pytest.mark.asyncio
async def test_delete_conversation_removes_local_conversation_and_related_data(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    created_at = datetime(2026, 8, 11, 8, 0, tzinfo=UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv-local"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        title="Delete me",
    )
    user_message = UserMessage(
        message_id=MessageId("msg-user"),
        conversation_id=conversation.conversation_id,
        content="Hello",
        created_at=created_at,
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
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
        await conversations.save(conversation)
        await starter.start(
            conversation=conversation,
            user_message=user_message,
            run=Run(
                run_id=RunId("run-local"),
                conversation_id=conversation.conversation_id,
                status=RunStatus.COMPLETED,
                created_at=created_at,
                updated_at=created_at,
            ),
        )

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.delete(
                "/api/v1/conversations/conv-local",
                headers={"Authorization": "Bearer test-token"},
            )

        stored_conversation = await conversations.get(conversation.conversation_id)
        stored_messages = await conversations.list_messages(
            conversation.conversation_id,
        )
        stored_runs = await runs.list_for_conversation(conversation.conversation_id)
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 204
    assert stored_conversation is None
    assert stored_messages == ()
    assert stored_runs == ()


@pytest.mark.asyncio
async def test_delete_conversation_hides_unknown_or_other_user_conversations(
    tmp_path: Path,
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
        runs=_UNUSED_RUNS,
        run_submission=_unused_run_submission(repository),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await repository.save(other_user_conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            missing = await client.delete(
                "/api/v1/conversations/missing",
                headers={"Authorization": "Bearer test-token"},
            )
            other_user = await client.delete(
                "/api/v1/conversations/conv-other-user",
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        await repository.aclose()

    assert missing.status_code == 404
    assert other_user.status_code == 404
    assert missing.json() == {"detail": "conversation not found"}
    assert other_user.json() == {"detail": "conversation not found"}


@pytest.mark.asyncio
async def test_submit_message_creates_a_visible_message_and_created_run(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation = _conversation(
        ConversationId("conv-local"),
        UserId("local-user"),
        datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
    )
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=lambda: created_at,
            new_run_id=lambda: RunId("run-created"),
            new_message_id=lambda: MessageId("msg-created"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/conversations/conv-local/messages",
                headers={"Authorization": "Bearer test-token"},
                json={"content": "Hello, asAgent."},
            )

        messages = await conversations.list_messages(conversation.conversation_id)
        persisted_runs = await runs.list_for_conversation(
            conversation.conversation_id,
        )
        stored_conversation = await conversations.get(conversation.conversation_id)
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 201
    assert response.json() == {
        "message": {
            "message_id": "msg-created",
            "role": "user",
            "content": "Hello, asAgent.",
            "created_at": "2026-08-11T12:00:00Z",
        },
        "run": {
            "run_id": "run-created",
            "status": "created",
            "created_at": "2026-08-11T12:00:00Z",
            "updated_at": "2026-08-11T12:00:00Z",
        },
        "conversation": {
            "conversation_id": "conv-local",
            "created_at": "2026-08-11T11:00:00Z",
            "updated_at": "2026-08-11T12:00:00Z",
            "title": "Hello, asAgent.",
        },
    }
    assert messages == (
        UserMessage(
            message_id=MessageId("msg-created"),
            conversation_id=conversation.conversation_id,
            content="Hello, asAgent.",
            created_at=created_at,
        ),
    )
    assert len(persisted_runs) == 1
    assert persisted_runs[0].run_id == RunId("run-created")
    assert persisted_runs[0].status is RunStatus.CREATED
    assert stored_conversation is not None
    assert stored_conversation.title == "Hello, asAgent."
    assert stored_conversation.updated_at == created_at


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    (
        {},
        {"content": ""},
        {"content": "   "},
        {"content": "Hello", "unexpected": True},
    ),
)
async def test_submit_message_rejects_invalid_request_bodies(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    database_path = tmp_path / "asagent.sqlite3"
    _upgrade(database_path)

    conversation = _conversation(
        ConversationId("conv-local"),
        UserId("local-user"),
        datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
    )
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
            new_run_id=lambda: RunId("run-created"),
            new_message_id=lambda: MessageId("msg-created"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/conversations/conv-local/messages",
                headers={"Authorization": "Bearer test-token"},
                json=payload,
            )

        messages = await conversations.list_messages(conversation.conversation_id)
        persisted_runs = await runs.list_for_conversation(
            conversation.conversation_id,
        )
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 422
    assert messages == ()
    assert persisted_runs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conversation_id",
    (
        "missing",
        "conv-other-user",
    ),
)
async def test_submit_message_hides_unknown_or_other_user_conversations(
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
    conversations = SqliteConversationRepository(database_path)
    runs = SqliteRunRepository(database_path)
    starter = SqliteRunStarter(database_path)
    app = create_app(
        access_token=LocalApiToken("test-token"),
        conversations=conversations,
        runs=runs,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=lambda: datetime(2026, 8, 11, 12, 0, tzinfo=UTC),
            new_run_id=lambda: RunId("run-created"),
            new_message_id=lambda: MessageId("msg-created"),
        ),
        dispatch_submitted_run=_discard_submission,
        cancel_run=_cancel_nothing,
    )
    transport = httpx.ASGITransport(app=app)

    try:
        await conversations.save(other_user_conversation)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers={"Authorization": "Bearer test-token"},
                json={"content": "Hello, asAgent."},
            )

        messages = await conversations.list_messages(
            ConversationId("conv-other-user"),
        )
        persisted_runs = await runs.list_for_conversation(
            ConversationId("conv-other-user"),
        )
    finally:
        await starter.aclose()
        await runs.aclose()
        await conversations.aclose()

    assert response.status_code == 404
    assert response.json() == {"detail": "conversation not found"}
    assert messages == ()
    assert persisted_runs == ()
