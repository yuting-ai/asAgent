from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from ragent.core.ids import ConversationId, MessageId
from ragent.core.messages import AssistantMessage, UserMessage


def test_user_message_preserves_visible_history_fields() -> None:
    created_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)

    message = UserMessage(
        message_id=MessageId("msg_user_123"),
        conversation_id=ConversationId("conv_123"),
        content="Hello, Ragent.",
        created_at=created_at,
    )

    assert message.message_id == "msg_user_123"
    assert message.conversation_id == "conv_123"
    assert message.content == "Hello, Ragent."
    assert message.created_at == created_at


def test_assistant_message_is_immutable() -> None:
    message = AssistantMessage(
        message_id=MessageId("msg_assistant_123"),
        conversation_id=ConversationId("conv_123"),
        content="Hello! How can I help?",
        created_at=datetime(2026, 7, 31, 12, 1, tzinfo=UTC),
    )

    with pytest.raises(FrozenInstanceError):
        message.content = "Changed"  # type: ignore[misc]
