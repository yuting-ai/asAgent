from datetime import datetime
from typing import Final, Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import UserId
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

    return app
