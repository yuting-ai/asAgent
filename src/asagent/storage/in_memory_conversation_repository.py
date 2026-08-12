from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, UserId
from asagent.core.messages import AssistantMessage, UserMessage


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._conversations: dict[ConversationId, Conversation] = {}
        self._messages: dict[
            ConversationId,
            list[UserMessage | AssistantMessage],
        ] = {}

    async def get(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None:
        return self._conversations.get(conversation_id)

    async def list_for_user(self, user_id: UserId) -> tuple[Conversation, ...]:
        return tuple(
            conversation
            for conversation in self._conversations.values()
            if conversation.user_id == user_id
        )

    async def save(self, conversation: Conversation) -> None:
        self._conversations[conversation.conversation_id] = conversation

    async def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> tuple[UserMessage | AssistantMessage, ...]:
        return tuple(self._messages.get(conversation_id, ()))

    async def append_message(
        self,
        message: UserMessage | AssistantMessage,
    ) -> None:
        if message.conversation_id not in self._conversations:
            raise ValueError("cannot append a message to an unknown conversation")

        self._messages.setdefault(message.conversation_id, []).append(message)

    async def delete(self, conversation_id: ConversationId) -> bool:
        if conversation_id not in self._conversations:
            return False

        del self._conversations[conversation_id]
        self._messages.pop(conversation_id, None)
        return True
