from datetime import UTC, datetime

import pytest

from asagent.agent.run_submission import (
    ConversationAccessDeniedError,
    RunSubmissionService,
    UnknownConversationError,
)
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.messages import UserMessage
from asagent.core.run import Run
from asagent.core.run_status import RunStatus
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

_LOCAL_USER_ID = UserId("local-user")


class RecordingRunStarter:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[Conversation, UserMessage, Run]] = []
        self._error = error

    async def start(
        self,
        *,
        conversation: Conversation,
        user_message: UserMessage,
        run: Run,
    ) -> None:
        self.calls.append((conversation, user_message, run))
        if self._error is not None:
            raise self._error


def _conversation(
    conversation_id: ConversationId,
    user_id: UserId = _LOCAL_USER_ID,
    *,
    title: str | None = None,
) -> Conversation:
    created_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=conversation_id,
        user_id=user_id,
        created_at=created_at,
        updated_at=created_at,
        title=title,
    )


def _service(
    *,
    conversations: InMemoryConversationRepository,
    starter: RecordingRunStarter,
) -> RunSubmissionService:
    created_at = datetime(2026, 8, 11, 12, 1, tzinfo=UTC)
    return RunSubmissionService(
        conversations=conversations,
        run_starter=starter,
        now=lambda: created_at,
        new_run_id=lambda: RunId("run-1"),
        new_message_id=lambda: MessageId("message-1"),
    )


@pytest.mark.asyncio
async def test_submit_creates_a_user_message_and_created_run() -> None:
    conversations = InMemoryConversationRepository()
    starter = RecordingRunStarter()
    conversation_id = ConversationId("conversation-1")
    await conversations.save(_conversation(conversation_id))

    submission = await _service(
        conversations=conversations,
        starter=starter,
    ).submit(
        conversation_id=conversation_id,
        content="Hello, asAgent.",
        user_id=_LOCAL_USER_ID,
    )

    assert submission.user_message.message_id == MessageId("message-1")
    assert submission.user_message.conversation_id == conversation_id
    assert submission.user_message.content == "Hello, asAgent."
    assert submission.run.run_id == RunId("run-1")
    assert submission.run.conversation_id == conversation_id
    assert submission.run.status is RunStatus.CREATED
    assert submission.user_message.created_at == submission.run.created_at
    assert submission.run.created_at == submission.run.updated_at
    assert submission.conversation.title == "Hello, asAgent."
    assert submission.conversation.updated_at == submission.run.created_at
    assert starter.calls == [
        (submission.conversation, submission.user_message, submission.run),
    ]


@pytest.mark.asyncio
async def test_submit_generates_a_normalized_and_truncated_title() -> None:
    conversations = InMemoryConversationRepository()
    starter = RecordingRunStarter()
    conversation_id = ConversationId("conversation-1")
    await conversations.save(_conversation(conversation_id))

    long_content = "  ".join(["word"] * 40)
    submission = await _service(
        conversations=conversations,
        starter=starter,
    ).submit(
        conversation_id=conversation_id,
        content=f"  {long_content}  ",
        user_id=_LOCAL_USER_ID,
    )

    normalized = " ".join(long_content.split())
    assert submission.conversation.title == f"{normalized[:59]}…"
    assert len(submission.conversation.title) == 60


@pytest.mark.asyncio
async def test_submit_keeps_an_existing_conversation_title() -> None:
    conversations = InMemoryConversationRepository()
    starter = RecordingRunStarter()
    conversation_id = ConversationId("conversation-1")
    await conversations.save(
        _conversation(conversation_id, title="Existing title"),
    )

    submission = await _service(
        conversations=conversations,
        starter=starter,
    ).submit(
        conversation_id=conversation_id,
        content="A newer message that should not replace the title.",
        user_id=_LOCAL_USER_ID,
    )

    assert submission.conversation.title == "Existing title"
    assert starter.calls[0][0].title == "Existing title"


@pytest.mark.asyncio
async def test_submit_rejects_unknown_or_inaccessible_conversation() -> None:
    conversations = InMemoryConversationRepository()
    starter = RecordingRunStarter()
    service = _service(conversations=conversations, starter=starter)

    with pytest.raises(UnknownConversationError):
        await service.submit(
            conversation_id=ConversationId("missing"),
            content="Hello",
            user_id=_LOCAL_USER_ID,
        )

    await conversations.save(
        _conversation(
            ConversationId("other-user"),
            UserId("other-user"),
        ),
    )
    with pytest.raises(ConversationAccessDeniedError):
        await service.submit(
            conversation_id=ConversationId("other-user"),
            content="Hello",
            user_id=_LOCAL_USER_ID,
        )

    assert starter.calls == []


@pytest.mark.asyncio
async def test_submit_propagates_run_starter_failure() -> None:
    conversations = InMemoryConversationRepository()
    expected_error = RuntimeError("database write failed")
    starter = RecordingRunStarter(expected_error)
    conversation_id = ConversationId("conversation-1")
    await conversations.save(_conversation(conversation_id))

    with pytest.raises(RuntimeError) as captured:
        await _service(
            conversations=conversations,
            starter=starter,
        ).submit(
            conversation_id=conversation_id,
            content="Hello",
        )

    assert captured.value is expected_error
    assert len(starter.calls) == 1
