from dataclasses import dataclass
from datetime import datetime

from asagent.core.ids import ConversationId, UserId


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: ConversationId
    user_id: UserId
    created_at: datetime
    updated_at: datetime
    title: str | None = None
