from datetime import datetime
from typing import Final, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository

_LOCAL_USER_ID: Final = UserId("local-user")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_conversation(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            conversation_id=str(conversation.conversation_id),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )


class MessageResponse(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    @classmethod
    def from_message(
        cls,
        message: UserMessage | AssistantMessage,
    ) -> "MessageResponse":
        role: Literal["user", "assistant"]
        if isinstance(message, UserMessage):
            role = "user"
        else:
            role = "assistant"

        return cls(
            message_id=str(message.message_id),
            role=role,
            content=message.content,
            created_at=message.created_at,
        )


def create_app(
    *,
    access_token: LocalApiToken,
    conversations: ConversationRepository,
) -> FastAPI:
    app = FastAPI(
        title="asAgent Local API",
        version="0.1.0",
    )
    authenticate = BearerTokenAuthenticator(access_token)

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        dependencies=[Depends(authenticate)],
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/api/v1/conversations",
        response_model=list[ConversationResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_conversations() -> list[ConversationResponse]:
        stored_conversations = await conversations.list_for_user(_LOCAL_USER_ID)
        return [
            ConversationResponse.from_conversation(conversation)
            for conversation in stored_conversations
        ]

    @app.get(
        "/api/v1/conversations/{conversation_id}/messages",
        response_model=list[MessageResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_conversation_messages(
        conversation_id: str,
    ) -> list[MessageResponse]:
        stored_conversation = await conversations.get(
            ConversationId(conversation_id),
        )

        if stored_conversation is None or stored_conversation.user_id != _LOCAL_USER_ID:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )

        stored_messages = await conversations.list_messages(
            stored_conversation.conversation_id,
        )
        return [MessageResponse.from_message(message) for message in stored_messages]

    return app
