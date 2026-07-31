from dataclasses import dataclass
from datetime import datetime

from ragent.core.ids import ConversationId, MessageId


@dataclass(frozen=True, slots=True)
class UserMessage:
    message_id: MessageId
    conversation_id: ConversationId
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    message_id: MessageId
    conversation_id: ConversationId
    content: str
    created_at: datetime
