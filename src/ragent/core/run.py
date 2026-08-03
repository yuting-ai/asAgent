from dataclasses import dataclass
from datetime import datetime

from ragent.core.ids import ConversationId, RunId
from ragent.core.run_status import RunStatus


@dataclass(frozen=True, slots=True)
class Run:
    run_id: RunId
    conversation_id: ConversationId
    status: RunStatus
    created_at: datetime
    updated_at: datetime
