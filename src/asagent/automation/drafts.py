from dataclasses import dataclass

from asagent.core.ids import AutomationId, ConversationId


@dataclass(frozen=True, slots=True)
class AutomationDraftContext:
    automation_id: AutomationId | None
    timezone: str


class AutomationDraftContextStore:
    """Process-local binding between a draft conversation and its saved automation."""

    def __init__(self) -> None:
        self._contexts: dict[ConversationId, AutomationDraftContext] = {}

    def bind(
        self,
        conversation_id: ConversationId,
        automation_id: AutomationId | None,
        timezone: str = "UTC",
    ) -> None:
        self._contexts[conversation_id] = AutomationDraftContext(
            automation_id=automation_id,
            timezone=timezone,
        )

    def target(self, conversation_id: ConversationId) -> AutomationId | None:
        context = self._contexts.get(conversation_id)
        return None if context is None else context.automation_id

    def timezone(self, conversation_id: ConversationId) -> str:
        return self._contexts[conversation_id].timezone

    def contains(self, conversation_id: ConversationId) -> bool:
        return conversation_id in self._contexts

    def remove(self, conversation_id: ConversationId) -> None:
        self._contexts.pop(conversation_id, None)
