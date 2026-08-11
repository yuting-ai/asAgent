from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator

from asagent.agent.run_submission import (
    ConversationAccessDeniedError,
    RunSubmissionService,
    SubmittedRun,
    UnknownConversationError,
)
from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository
from asagent.core.run import Run

_LOCAL_USER_ID: Final = UserId("local-user")


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class CreateMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class RunResponse(BaseModel):
    run_id: str
    status: Literal["created"]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_run(cls, run: Run) -> "RunResponse":
        return cls(
            run_id=str(run.run_id),
            status="created",
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class SubmitMessageResponse(BaseModel):
    message: MessageResponse
    run: RunResponse


def create_app(
    *,
    access_token: LocalApiToken,
    conversations: ConversationRepository,
    run_submission: RunSubmissionService,
    dispatch_submitted_run: Callable[[SubmittedRun], object],
    conversation_id_factory: Callable[[], ConversationId] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="asAgent Local API",
        version="0.1.0",
    )
    authenticate = BearerTokenAuthenticator(access_token)
    create_conversation_id = conversation_id_factory or _new_conversation_id
    current_time = clock or _now

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

    @app.post(
        "/api/v1/conversations",
        response_model=ConversationResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def create_conversation(
        request: CreateConversationRequest,
    ) -> ConversationResponse:
        del request

        created_at = current_time()
        conversation = Conversation(
            conversation_id=create_conversation_id(),
            user_id=_LOCAL_USER_ID,
            created_at=created_at,
            updated_at=created_at,
        )
        await conversations.save(conversation)

        return ConversationResponse.from_conversation(conversation)

    @app.post(
        "/api/v1/conversations/{conversation_id}/messages",
        response_model=SubmitMessageResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def submit_message(
        conversation_id: str,
        request: CreateMessageRequest,
    ) -> SubmitMessageResponse:
        try:
            submission = await run_submission.submit(
                conversation_id=ConversationId(conversation_id),
                content=request.content,
                user_id=_LOCAL_USER_ID,
            )
        except (
            UnknownConversationError,
            ConversationAccessDeniedError,
        ) as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            ) from error

        dispatch_submitted_run(submission)

        return SubmitMessageResponse(
            message=MessageResponse.from_message(submission.user_message),
            run=RunResponse.from_run(submission.run),
        )

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


def _new_conversation_id() -> ConversationId:
    return ConversationId(f"conv_{uuid4().hex}")


def _now() -> datetime:
    return datetime.now(UTC)
