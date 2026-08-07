from collections.abc import Callable
from datetime import datetime

from asagent.core.conversation import Conversation
from asagent.core.ids import MessageId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository
from asagent.models.contracts import (
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
)
from asagent.models.provider import ModelProvider


class ChatService:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        model_provider: ModelProvider,
        now: Callable[[], datetime],
        new_message_id: Callable[[], MessageId],
    ) -> None:
        self._conversations = conversations
        self._model_provider = model_provider
        self._now = now
        self._new_message_id = new_message_id

    async def send(
        self,
        *,
        conversation: Conversation,
        content: str,
        model_name: str,
        system_prompt: str,
    ) -> AssistantMessage:
        await self._conversations.save(conversation)

        user_message = UserMessage(
            message_id=self._new_message_id(),
            conversation_id=conversation.conversation_id,
            content=content,
            created_at=self._now(),
        )
        await self._conversations.append_message(user_message)

        history = await self._conversations.list_messages(
            conversation.conversation_id,
        )
        response = await self._model_provider.complete(
            ModelRequest(
                model=model_name,
                system_prompt=system_prompt,
                messages=tuple(self._to_model_message(message) for message in history),
                tools=(),
            ),
        )

        if response.text is None or response.tool_calls:
            raise ValueError(
                "minimal ChatService requires a text response without tool calls",
            )

        assistant_message = AssistantMessage(
            message_id=self._new_message_id(),
            conversation_id=conversation.conversation_id,
            content=response.text,
            created_at=self._now(),
        )
        await self._conversations.append_message(assistant_message)
        return assistant_message

    @staticmethod
    def _to_model_message(
        message: UserMessage | AssistantMessage,
    ) -> ModelMessage:
        if isinstance(message, UserMessage):
            role = ModelMessageRole.USER
        else:
            role = ModelMessageRole.ASSISTANT

        return ModelMessage(role=role, content=message.content)
