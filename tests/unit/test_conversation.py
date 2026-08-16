from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, UserId


def test_conversation_preserves_identity_owner_and_timestamps() -> None:
    created_at = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 8, 4, 9, 1, tzinfo=UTC)

    conversation = Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=updated_at,
    )

    assert conversation.conversation_id == "conv_123"
    assert conversation.user_id == "local-user"
    assert conversation.created_at == created_at
    assert conversation.updated_at == updated_at
    assert conversation.kind == "chat"


def test_conversation_defaults_to_chat_kind() -> None:
    created_at = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )

    assert conversation.kind == "chat"


def test_conversation_preserves_browser_kind() -> None:
    created_at = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv_browser"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        kind="browser",
    )

    assert conversation.kind == "browser"


def test_conversation_is_immutable() -> None:
    created_at = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(  # noqa: B010
            conversation,
            "updated_at",
            datetime(2026, 8, 4, 9, 1, tzinfo=UTC),
        )
