from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from ragent.core.ids import ConversationId, EventId, RunId


@dataclass(frozen=True, slots=True)
class RunEvent:
    event_id: EventId
    run_id: RunId
    conversation_id: ConversationId
    sequence: int
    event_type: str
    created_at: datetime
    data: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence must be at least 1")

        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))
