from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from asagent.core.ids import ConversationId, UserId

ConversationKind = Literal[
    "chat",
    "browser",
    "automation_draft",
    "automation_execution",
    "knowledge",
]


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: ConversationId
    user_id: UserId
    created_at: datetime
    updated_at: datetime
    title: str | None = None
    kind: ConversationKind = "chat"
    last_page_url: str | None = None
    last_page_title: str | None = None
