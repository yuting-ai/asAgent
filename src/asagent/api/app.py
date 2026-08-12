import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Annotated, Final, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator

from asagent.agent.run_submission import (
    ConversationAccessDeniedError,
    RunSubmissionService,
    SubmittedRun,
    UnknownConversationError,
)
from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken
from asagent.core.conversation import Conversation
from asagent.core.ids import ApprovalId, ConversationId, RunId, UserId
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import ConversationRepository, RunRepository
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.tools.approval import PendingToolApprovalPolicy, ToolApprovalRequest

_LOCAL_USER_ID: Final = UserId("local-user")
_EVENT_POLL_INTERVAL_SECONDS: Final = 0.1


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None

    @classmethod
    def from_conversation(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            conversation_id=str(conversation.conversation_id),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            title=conversation.title,
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
    status: RunStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_run(cls, run: Run) -> "RunResponse":
        return cls(
            run_id=str(run.run_id),
            status=run.status,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )


class CancelRunResponse(BaseModel):
    run_id: str
    cancellation_requested: Literal[True] = True


class SubmitMessageResponse(BaseModel):
    message: MessageResponse
    run: RunResponse
    conversation: ConversationResponse


class ToolApprovalResponse(BaseModel):
    approval_id: str
    run_id: str
    conversation_id: str
    tool_call_id: str
    tool_id: str
    display_name: str
    description: str
    arguments: dict[str, object]

    @classmethod
    def from_request(cls, request: ToolApprovalRequest) -> "ToolApprovalResponse":
        return cls(
            approval_id=str(request.approval_id),
            run_id=str(request.run_id),
            conversation_id=str(request.conversation_id),
            tool_call_id=request.tool_call_id,
            tool_id=request.definition.tool_id,
            display_name=request.definition.display_name,
            description=request.definition.description,
            arguments=dict(request.arguments),
        )


class ToolApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


class ToolApprovalDecisionResponse(BaseModel):
    approval_id: str
    approved: bool


def create_app(
    *,
    access_token: LocalApiToken,
    conversations: ConversationRepository,
    runs: RunRepository,
    run_submission: RunSubmissionService,
    dispatch_submitted_run: Callable[[SubmittedRun], object],
    cancel_run: Callable[[RunId], bool],
    tool_approvals: PendingToolApprovalPolicy | None = None,
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

    async def get_local_run(run_id: RunId) -> Run:
        stored_run = await runs.get(run_id)
        if stored_run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="run not found",
            )

        conversation = await conversations.get(stored_run.conversation_id)
        if conversation is None or conversation.user_id != _LOCAL_USER_ID:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="run not found",
            )

        return stored_run

    async def get_pending_approval(approval_id: ApprovalId) -> ToolApprovalRequest:
        if tool_approvals is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="tool approval not found",
            )

        pending = tool_approvals.get(approval_id)
        if pending is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="tool approval not found",
            )

        await get_local_run(pending.run_id)
        return pending

    def event_frame(event: RunEvent) -> str:
        payload = {
            "event_id": str(event.event_id),
            "run_id": str(event.run_id),
            "conversation_id": str(event.conversation_id),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "created_at": event.created_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "data": dict(event.data),
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return (
            f"id: {event.sequence}\nevent: {event.event_type}\ndata: {serialized}\n\n"
        )

    async def stream_events(
        *,
        request: Request,
        run_id: RunId,
        after_sequence: int,
    ) -> AsyncIterator[str]:
        current_sequence = after_sequence

        while True:
            events = await runs.list_events(
                run_id,
                after_sequence=current_sequence,
            )
            for event in events:
                current_sequence = event.sequence
                yield event_frame(event)

            stored_run = await runs.get(run_id)
            if stored_run is None or stored_run.status.is_terminal:
                return

            if await request.is_disconnected():
                return

            await asyncio.sleep(_EVENT_POLL_INTERVAL_SECONDS)

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
            conversation=ConversationResponse.from_conversation(
                submission.conversation,
            ),
        )

    @app.get(
        "/api/v1/runs/{run_id}",
        response_model=RunResponse,
        dependencies=[Depends(authenticate)],
    )
    async def get_run(run_id: str) -> RunResponse:
        stored_run = await get_local_run(RunId(run_id))
        return RunResponse.from_run(stored_run)

    @app.get(
        "/api/v1/runs/{run_id}/events",
        dependencies=[Depends(authenticate)],
    )
    async def stream_run_events(
        request: Request,
        run_id: str,
        after_sequence: Annotated[int, Query(ge=0)] = 0,
    ) -> StreamingResponse:
        stored_run = await get_local_run(RunId(run_id))

        return StreamingResponse(
            stream_events(
                request=request,
                run_id=stored_run.run_id,
                after_sequence=after_sequence,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.post(
        "/api/v1/runs/{run_id}/cancel",
        response_model=CancelRunResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(authenticate)],
    )
    async def cancel_run_request(run_id: str) -> CancelRunResponse:
        stored_run = await get_local_run(RunId(run_id))

        if not cancel_run(stored_run.run_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="run is not active",
            )

        if tool_approvals is not None:
            tool_approvals.deny_run(stored_run.run_id)

        return CancelRunResponse(run_id=str(stored_run.run_id))

    @app.get(
        "/api/v1/tool-approvals/{approval_id}",
        response_model=ToolApprovalResponse,
        dependencies=[Depends(authenticate)],
    )
    async def get_tool_approval(approval_id: str) -> ToolApprovalResponse:
        pending = await get_pending_approval(ApprovalId(approval_id))
        return ToolApprovalResponse.from_request(pending)

    @app.post(
        "/api/v1/tool-approvals/{approval_id}/decision",
        response_model=ToolApprovalDecisionResponse,
        dependencies=[Depends(authenticate)],
    )
    async def decide_tool_approval(
        approval_id: str,
        request: ToolApprovalDecisionRequest,
    ) -> ToolApprovalDecisionResponse:
        pending = await get_pending_approval(ApprovalId(approval_id))
        assert tool_approvals is not None

        if not tool_approvals.decide(pending.approval_id, request.approved):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="tool approval not found",
            )

        return ToolApprovalDecisionResponse(
            approval_id=str(pending.approval_id),
            approved=request.approved,
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
