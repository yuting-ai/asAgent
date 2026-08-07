from typing import assert_type

from asagent.core.ids import (
    ConversationId,
    EventId,
    MessageId,
    RunId,
    ToolCallId,
    UserId,
)


def test_id_types_preserve_string_values() -> None:
    user_id = UserId("local-user")
    conversation_id = ConversationId("conv_123")
    run_id = RunId("run_123")
    tool_call_id = ToolCallId("tool_123")
    event_id = EventId("evt_123")
    message_id = MessageId("msg_123")

    assert user_id == "local-user"
    assert conversation_id == "conv_123"
    assert run_id == "run_123"
    assert tool_call_id == "tool_123"
    assert event_id == "evt_123"
    assert message_id == "msg_123"

    assert isinstance(user_id, str)
    assert isinstance(conversation_id, str)
    assert isinstance(run_id, str)
    assert isinstance(tool_call_id, str)
    assert isinstance(event_id, str)
    assert isinstance(message_id, str)

    assert_type(user_id, UserId)
    assert_type(conversation_id, ConversationId)
    assert_type(run_id, RunId)
    assert_type(tool_call_id, ToolCallId)
    assert_type(event_id, EventId)
    assert_type(message_id, MessageId)
