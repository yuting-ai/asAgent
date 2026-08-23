import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Annotated, Final, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import Response, StreamingResponse
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from asagent.agent.run_submission import (
    ConversationAccessDeniedError,
    RunSubmissionService,
    SubmittedRun,
    UnknownConversationError,
)
from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken
from asagent.automation.drafts import AutomationDraftContextStore
from asagent.bootstrap.agent_settings import (
    MAX_MAX_STEPS,
    MIN_MAX_STEPS,
    AgentSettings,
    AgentSettingsStore,
)
from asagent.bootstrap.model_settings import (
    ModelApiKeyMissingError,
    ModelSettings,
    ModelSettingsIssue,
    ModelSettingsStatus,
)
from asagent.bootstrap.storage_settings import (
    StorageSettings,
    StorageSettingsStore,
)
from asagent.bootstrap.tavily_settings import (
    TavilyApiKeyMissingError,
    TavilySettings,
    TavilySettingsStatus,
)
from asagent.core.automation import (
    Automation,
    AutomationExecution,
    AutomationStatus,
    AutomationTrigger,
    AutomationTriggerKind,
    next_run_after,
)
from asagent.core.conversation import Conversation, ConversationKind
from asagent.core.file_change import FileChange
from asagent.core.ids import (
    ApprovalId,
    AutomationExecutionId,
    AutomationId,
    AutomationTriggerId,
    ConversationId,
    FileChangeId,
    RunId,
    UserId,
)
from asagent.core.messages import AssistantMessage, UserMessage
from asagent.core.repositories import (
    AutomationRepository,
    ConversationRepository,
    FileChangeRepository,
    RunRepository,
)
from asagent.core.run import Run
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.models.config import ProviderLocation
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.reversible_files import (
    FileChangeConflictError,
    FileChangeNotFoundError,
)
from asagent.tools.approval import (
    PendingToolApprovalPolicy,
    ToolApprovalDecision,
    ToolApprovalRequest,
)
from asagent.tools.browser_run_bindings import BrowserRunBindings
from asagent.workspace.settings import (
    ConversationWorkspaceSettings,
    WorkspaceSettingsStatus,
)

_LOCAL_USER_ID: Final = UserId("local-user")
_EVENT_POLL_INTERVAL_SECONDS: Final = 0.1


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class AutomationResponse(BaseModel):
    automation_id: str
    name: str
    plan_summary: str
    allowed_capabilities: list[str]
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_automation(cls, value: Automation) -> "AutomationResponse":
        return cls(
            automation_id=str(value.automation_id),
            name=value.name,
            plan_summary=value.plan_summary,
            allowed_capabilities=list(value.allowed_capabilities),
            status=value.status.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
        )


class AutomationTriggerResponse(BaseModel):
    automation_trigger_id: str
    kind: str
    timezone: str
    local_time: str
    weekday: int | None
    next_run_at: datetime | None
    enabled: bool

    @classmethod
    def from_trigger(cls, value: AutomationTrigger) -> "AutomationTriggerResponse":
        return cls(
            automation_trigger_id=str(value.automation_trigger_id),
            kind=value.kind.value,
            timezone=value.timezone,
            local_time=value.local_time.isoformat(),
            weekday=value.weekday,
            next_run_at=value.next_run_at,
            enabled=value.enabled,
        )


class AutomationExecutionResponse(BaseModel):
    automation_execution_id: str
    scheduled_for: datetime
    status: str
    run_id: str | None
    claimed_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_execution(
        cls, value: AutomationExecution
    ) -> "AutomationExecutionResponse":
        return cls(
            automation_execution_id=str(value.automation_execution_id),
            scheduled_for=value.scheduled_for,
            status=value.status.value,
            run_id=None if value.run_id is None else str(value.run_id),
            claimed_at=value.claimed_at,
            completed_at=value.completed_at,
        )


class UpdateAutomationStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["draft", "active", "paused"]


class CreateAutomationTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["once", "daily", "weekly"]
    timezone: str
    local_time: str
    weekday: int | None = None
    next_run_at: datetime | None = None


class CreateAutomationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    plan_summary: str
    allowed_capabilities: list[str] = Field(default_factory=list)
    trigger: CreateAutomationTriggerRequest

    @field_validator("name", "plan_summary")
    @classmethod
    def automation_text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class UpdateAutomationRequest(CreateAutomationRequest):
    """Full replacement of the editable automation plan and its single trigger."""


class CreateAutomationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automation_id: str | None = None
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def timezone_must_be_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("timezone must not be blank")
        return value.strip()


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("title must not be blank")
        if len(normalized) <= 60:
            return normalized
        return f"{normalized[:59]}…"


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    updated_at: datetime
    title: str | None
    last_page_url: str | None
    last_page_title: str | None

    @classmethod
    def from_conversation(cls, conversation: Conversation) -> "ConversationResponse":
        return cls(
            conversation_id=str(conversation.conversation_id),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            title=conversation.title,
            last_page_url=conversation.last_page_url,
            last_page_title=conversation.last_page_title,
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


class CreateAutomationDraftMessageRequest(CreateMessageRequest):
    tab_id: str | None = None

    @field_validator("tab_id")
    @classmethod
    def tab_id_must_be_valid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        tab_id = value.strip()
        if (
            not tab_id
            or len(tab_id) > 80
            or any(
                not character.isalnum() and character not in "-_"
                for character in tab_id
            )
        ):
            raise ValueError("tab_id is invalid")
        return tab_id


class CreateBrowserMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    tab_id: str
    last_page_url: str | None = None
    last_page_title: str | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value

    @field_validator("tab_id")
    @classmethod
    def tab_id_must_be_valid(cls, value: str) -> str:
        tab_id = value.strip()
        if not tab_id:
            raise ValueError("tab_id must not be blank")
        if len(tab_id) > 80 or any(
            not character.isalnum() and character not in "-_" for character in tab_id
        ):
            raise ValueError("tab_id is invalid")
        return tab_id

    @field_validator("last_page_url")
    @classmethod
    def last_page_url_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if len(normalized) > 2048:
            raise ValueError("last_page_url is too long")
        try:
            parsed = urlsplit(normalized)
            hostname = parsed.hostname
        except ValueError as error:
            raise ValueError("last_page_url is invalid") from error
        if (
            parsed.scheme not in {"http", "https"}
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("last_page_url is invalid")
        return normalized

    @field_validator("last_page_title")
    @classmethod
    def last_page_title_must_be_bounded(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            return None
        return normalized[:200]


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


class RunEventResponse(BaseModel):
    event_type: str
    created_at: datetime
    data: dict[str, object]

    @classmethod
    def from_event(cls, event: RunEvent) -> "RunEventResponse":
        return cls(
            event_type=event.event_type,
            created_at=event.created_at,
            data=dict(event.data),
        )


class RunHistoryResponse(BaseModel):
    run: RunResponse
    events: list[RunEventResponse]


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
    resource_path: str | None = None
    impact_summary: str | None = None
    allows_conversation_approval: bool = True

    @classmethod
    def from_request(cls, request: ToolApprovalRequest) -> "ToolApprovalResponse":
        arguments = dict(request.arguments)
        resource_path: str | None = None
        impact_summary: str | None = None
        summaries = {
            "filesystem.create_file": "Create a new UTF-8 text file.",
            "filesystem.replace_file": (
                "Replace this UTF-8 text file and save a private undo snapshot."
            ),
            "filesystem.delete_file": (
                "Delete this file and move it to the Trash with an undo snapshot."
            ),
        }
        if request.definition.tool_id in summaries:
            path = arguments.get("path")
            resource_path = path if isinstance(path, str) else None
            arguments = {"path": resource_path} if resource_path is not None else {}
            impact_summary = summaries[request.definition.tool_id]
        return cls(
            approval_id=str(request.approval_id),
            run_id=str(request.run_id),
            conversation_id=str(request.conversation_id),
            tool_call_id=request.tool_call_id,
            tool_id=request.definition.tool_id,
            display_name=request.definition.display_name,
            description=request.definition.description,
            arguments=arguments,
            resource_path=resource_path,
            impact_summary=impact_summary,
            allows_conversation_approval=(
                request.definition.allows_conversation_approval
            ),
        )


class FileChangeResponse(BaseModel):
    change_id: str
    run_id: str
    operation: str
    status: str
    path: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_change(cls, change: FileChange) -> "FileChangeResponse":
        return cls(
            change_id=str(change.file_change_id),
            run_id=str(change.run_id),
            operation=change.operation.value,
            status=change.status.value,
            path=str(Path(change.root_path) / change.relative_path),
            created_at=change.created_at,
            updated_at=change.updated_at,
        )


class UndoFileChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str

    @field_validator("path")
    @classmethod
    def path_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("path must not be blank")
        return value


class ToolApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ToolApprovalDecision


class ToolApprovalDecisionResponse(BaseModel):
    approval_id: str
    decision: ToolApprovalDecision


class TavilySettingsResponse(BaseModel):
    enabled: bool
    api_key_saved: bool

    @classmethod
    def from_status(cls, status: TavilySettingsStatus) -> "TavilySettingsResponse":
        return cls(
            enabled=status.enabled,
            api_key_saved=status.api_key_saved,
        )


class SavedProviderConfigResponse(BaseModel):
    location: ProviderLocation
    model: str
    base_url: str
    api_key_saved: bool


class ModelSettingsResponse(BaseModel):
    configured: bool
    active: bool
    issue: ModelSettingsIssue | None
    location: ProviderLocation | None
    api_key_saved: bool
    model: str | None
    base_url: str | None
    saved_providers: dict[str, SavedProviderConfigResponse] = Field(
        default_factory=dict
    )

    @classmethod
    def from_status(cls, status: ModelSettingsStatus) -> "ModelSettingsResponse":
        return cls(
            configured=status.configured,
            active=status.active,
            issue=status.issue,
            location=status.location,
            api_key_saved=status.api_key_saved,
            model=status.model,
            base_url=status.base_url,
            saved_providers={
                k: SavedProviderConfigResponse(
                    location=v.location,
                    model=v.model,
                    base_url=v.base_url,
                    api_key_saved=v.api_key_saved,
                )
                for k, v in status.saved_providers.items()
            },
        )


class UpdateModelSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: ProviderLocation = ProviderLocation.EXTERNAL
    model: str = Field(min_length=1)
    base_url: AnyHttpUrl
    api_key: str | None = None

    @field_validator("model")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("api_key must not be blank")
        return value


class AgentSettingsResponse(BaseModel):
    max_steps: int

    @classmethod
    def from_settings(cls, settings: AgentSettings) -> "AgentSettingsResponse":
        return cls(max_steps=settings.max_steps)


class UpdateAgentSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(ge=MIN_MAX_STEPS, le=MAX_MAX_STEPS)

    @field_validator("max_steps", mode="before")
    @classmethod
    def max_steps_must_be_strict_int(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("max_steps must be an integer")
        return value


class UpdateTavilySettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key: str | None = None

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("api_key must not be blank")
        return value


class WorkspaceSettingsResponse(BaseModel):
    workspace_root: str
    additional_roots: list[str]
    additional_files: list[str]

    @classmethod
    def from_status(
        cls, status: WorkspaceSettingsStatus
    ) -> "WorkspaceSettingsResponse":
        return cls(
            workspace_root=str(status.workspace_root),
            additional_roots=[str(root) for root in status.additional_roots],
            additional_files=[str(file_path) for file_path in status.additional_files],
        )


class UpdateWorkspaceSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    additional_roots: list[str] = Field(max_length=16)
    additional_files: list[str] = Field(max_length=16)

    @field_validator("additional_roots")
    @classmethod
    def additional_roots_must_be_nonblank(cls, value: list[str]) -> list[str]:
        if any(not root.strip() for root in value):
            raise ValueError("additional_roots must not contain blank paths")
        return value

    @field_validator("additional_files")
    @classmethod
    def additional_files_must_be_nonblank(cls, value: list[str]) -> list[str]:
        if any(not file_path.strip() for file_path in value):
            raise ValueError("additional_files must not contain blank paths")
        return value


class StorageSettingsResponse(BaseModel):
    snapshot_retention_days: int
    usage_bytes: int
    snapshot_count: int


class UpdateStorageSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_retention_days: int


class ClearStorageResponse(BaseModel):
    freed_bytes: int
    deleted_count: int


def create_app(
    *,
    access_token: LocalApiToken,
    conversations: ConversationRepository,
    runs: RunRepository,
    run_submission: RunSubmissionService,
    dispatch_submitted_run: Callable[[SubmittedRun], object],
    cancel_run: Callable[[RunId], bool],
    tool_approvals: PendingToolApprovalPolicy | None = None,
    tavily_settings: TavilySettings | None = None,
    model_settings: ModelSettings | None = None,
    agent_settings: AgentSettingsStore | None = None,
    storage_settings: StorageSettingsStore | None = None,
    file_change_snapshots: FileChangeSnapshotStore | None = None,
    workspace_settings: ConversationWorkspaceSettings | None = None,
    file_changes: FileChangeRepository | None = None,
    revert_file_change: (
        Callable[[FileChangeId, Path], Awaitable[FileChange]] | None
    ) = None,
    browser_run_bindings: BrowserRunBindings | None = None,
    automations: AutomationRepository | None = None,
    automation_drafts: AutomationDraftContextStore | None = None,
    run_automation_now_action: Callable[[AutomationId], Awaitable[AutomationExecution]]
    | None = None,
    automation_id_factory: Callable[[], AutomationId] | None = None,
    automation_trigger_id_factory: Callable[[], AutomationTriggerId] | None = None,
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
    create_automation_id = automation_id_factory or _new_automation_id
    create_automation_trigger_id = (
        automation_trigger_id_factory or _new_automation_trigger_id
    )

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

    async def get_local_conversation(
        conversation_id: ConversationId,
        *,
        kind: ConversationKind,
    ) -> Conversation:
        conversation = await conversations.get(conversation_id)
        if (
            conversation is None
            or conversation.user_id != _LOCAL_USER_ID
            or conversation.kind != kind
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )
        return conversation

    async def list_conversations_of_kind(
        kind: ConversationKind,
    ) -> list[ConversationResponse]:
        stored_conversations = await conversations.list_for_user(
            _LOCAL_USER_ID,
            kind=kind,
        )
        return [
            ConversationResponse.from_conversation(conversation)
            for conversation in stored_conversations
        ]

    async def create_conversation_of_kind(
        kind: ConversationKind,
    ) -> ConversationResponse:
        created_at = current_time()
        conversation = Conversation(
            conversation_id=create_conversation_id(),
            user_id=_LOCAL_USER_ID,
            created_at=created_at,
            updated_at=created_at,
            kind=kind,
        )
        await conversations.save(conversation)
        return ConversationResponse.from_conversation(conversation)

    async def submit_message_of_kind(
        conversation_id: str,
        request: CreateMessageRequest,
        *,
        kind: ConversationKind,
        browser_tab_id: str | None = None,
    ) -> SubmitMessageResponse:
        await get_local_conversation(ConversationId(conversation_id), kind=kind)
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

        if browser_tab_id is not None and browser_run_bindings is not None:
            browser_run_bindings.bind(submission.run.run_id, browser_tab_id)
        dispatch_submitted_run(submission)

        return SubmitMessageResponse(
            message=MessageResponse.from_message(submission.user_message),
            run=RunResponse.from_run(submission.run),
            conversation=ConversationResponse.from_conversation(
                submission.conversation,
            ),
        )

    async def list_messages_of_kind(
        conversation_id: str,
        *,
        kind: ConversationKind,
    ) -> list[MessageResponse]:
        stored_conversation = await get_local_conversation(
            ConversationId(conversation_id),
            kind=kind,
        )
        stored_messages = await conversations.list_messages(
            stored_conversation.conversation_id,
        )
        return [MessageResponse.from_message(message) for message in stored_messages]

    async def list_run_history_of_kind(
        conversation_id: str,
        *,
        kind: ConversationKind,
    ) -> list[RunHistoryResponse]:
        stored_conversation = await get_local_conversation(
            ConversationId(conversation_id), kind=kind
        )
        stored_runs = await runs.list_for_conversation(
            stored_conversation.conversation_id
        )
        return [
            RunHistoryResponse(
                run=RunResponse.from_run(run),
                events=[
                    RunEventResponse.from_event(event)
                    for event in await runs.list_events(run.run_id)
                ],
            )
            for run in stored_runs
        ]

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
        return await list_conversations_of_kind("chat")

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
        return await create_conversation_of_kind("chat")

    @app.patch(
        "/api/v1/conversations/{conversation_id}",
        response_model=ConversationResponse,
        dependencies=[Depends(authenticate)],
    )
    async def update_conversation(
        conversation_id: str,
        request: UpdateConversationRequest,
    ) -> ConversationResponse:
        conversation = await get_local_conversation(
            ConversationId(conversation_id),
            kind="chat",
        )
        updated = replace(
            conversation,
            title=request.title,
        )
        await conversations.save(updated)
        return ConversationResponse.from_conversation(updated)

    @app.delete(
        "/api/v1/conversations/{conversation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(authenticate)],
    )
    async def delete_conversation(conversation_id: str) -> Response:
        await get_local_conversation(ConversationId(conversation_id), kind="chat")
        deleted = await conversations.delete(ConversationId(conversation_id))
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

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
        return await submit_message_of_kind(
            conversation_id,
            request,
            kind="chat",
        )

    @app.post(
        "/api/v1/automation-drafts",
        response_model=ConversationResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def create_automation_draft(
        request: CreateAutomationDraftRequest,
    ) -> ConversationResponse:
        target_id = (
            None
            if request.automation_id is None
            else AutomationId(request.automation_id)
        )
        if target_id is not None:
            target = None if automations is None else await automations.get(target_id)
            if target is None or target.user_id != _LOCAL_USER_ID:
                raise HTTPException(status_code=404, detail="automation not found")
        created = await create_conversation_of_kind("automation_draft")
        if automation_drafts is not None:
            automation_drafts.bind(
                ConversationId(created.conversation_id),
                target_id,
                request.timezone,
            )
        return created

    @app.get(
        "/api/v1/automation-drafts/{conversation_id}/messages",
        response_model=list[MessageResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_automation_draft_messages(
        conversation_id: str,
    ) -> list[MessageResponse]:
        return await list_messages_of_kind(conversation_id, kind="automation_draft")

    @app.post(
        "/api/v1/automation-drafts/{conversation_id}/messages",
        response_model=SubmitMessageResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def submit_automation_draft_message(
        conversation_id: str, request: CreateAutomationDraftMessageRequest
    ) -> SubmitMessageResponse:
        return await submit_message_of_kind(
            conversation_id,
            request,
            kind="automation_draft",
            browser_tab_id=request.tab_id,
        )

    @app.delete(
        "/api/v1/automation-drafts/{conversation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(authenticate)],
    )
    async def delete_automation_draft(conversation_id: str) -> Response:
        await get_local_conversation(
            ConversationId(conversation_id), kind="automation_draft"
        )
        await conversations.delete(ConversationId(conversation_id))
        if automation_drafts is not None:
            automation_drafts.remove(ConversationId(conversation_id))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

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

        if not tool_approvals.decide(pending.approval_id, request.decision):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="tool approval not found",
            )

        return ToolApprovalDecisionResponse(
            approval_id=str(pending.approval_id),
            decision=request.decision,
        )

    @app.get(
        "/api/v1/conversations/{conversation_id}/messages",
        response_model=list[MessageResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_conversation_messages(
        conversation_id: str,
    ) -> list[MessageResponse]:
        return await list_messages_of_kind(conversation_id, kind="chat")

    @app.get(
        "/api/v1/conversations/{conversation_id}/run-history",
        response_model=list[RunHistoryResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_conversation_run_history(
        conversation_id: str,
    ) -> list[RunHistoryResponse]:
        return await list_run_history_of_kind(conversation_id, kind="chat")

    @app.get(
        "/api/v1/browser/conversations",
        response_model=list[ConversationResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_browser_conversations() -> list[ConversationResponse]:
        return await list_conversations_of_kind("browser")

    @app.post(
        "/api/v1/browser/conversations",
        response_model=ConversationResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def create_browser_conversation(
        request: CreateConversationRequest,
    ) -> ConversationResponse:
        del request
        return await create_conversation_of_kind("browser")

    @app.delete(
        "/api/v1/browser/conversations/{conversation_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(authenticate)],
    )
    async def delete_browser_conversation(conversation_id: str) -> Response:
        await get_local_conversation(ConversationId(conversation_id), kind="browser")
        deleted = await conversations.delete(ConversationId(conversation_id))
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get(
        "/api/v1/browser/conversations/{conversation_id}/messages",
        response_model=list[MessageResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_browser_conversation_messages(
        conversation_id: str,
    ) -> list[MessageResponse]:
        return await list_messages_of_kind(conversation_id, kind="browser")

    @app.get(
        "/api/v1/browser/conversations/{conversation_id}/run-history",
        response_model=list[RunHistoryResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_browser_conversation_run_history(
        conversation_id: str,
    ) -> list[RunHistoryResponse]:
        return await list_run_history_of_kind(conversation_id, kind="browser")

    @app.post(
        "/api/v1/browser/conversations/{conversation_id}/messages",
        response_model=SubmitMessageResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(authenticate)],
    )
    async def submit_browser_message(
        conversation_id: str,
        request: CreateBrowserMessageRequest,
    ) -> SubmitMessageResponse:
        await get_local_conversation(ConversationId(conversation_id), kind="browser")
        try:
            submission = await run_submission.submit(
                conversation_id=ConversationId(conversation_id),
                content=request.content,
                user_id=_LOCAL_USER_ID,
                last_page_url=request.last_page_url,
                last_page_title=request.last_page_title,
            )
        except (
            UnknownConversationError,
            ConversationAccessDeniedError,
        ) as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="conversation not found",
            ) from error

        if browser_run_bindings is not None:
            browser_run_bindings.bind(submission.run.run_id, request.tab_id)

        dispatch_submitted_run(submission)

        return SubmitMessageResponse(
            message=MessageResponse.from_message(submission.user_message),
            run=RunResponse.from_run(submission.run),
            conversation=ConversationResponse.from_conversation(
                submission.conversation,
            ),
        )

    @app.get(
        "/api/v1/conversations/{conversation_id}/file-changes",
        response_model=list[FileChangeResponse],
        dependencies=[Depends(authenticate)],
    )
    async def list_conversation_file_changes(
        conversation_id: str,
    ) -> list[FileChangeResponse]:
        conversation = await get_local_conversation(
            ConversationId(conversation_id), kind="chat"
        )
        if file_changes is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="file changes are unavailable",
            )
        conversation_runs = await runs.list_for_conversation(
            conversation.conversation_id
        )
        changes = [
            change
            for run in conversation_runs
            for change in await file_changes.list_for_run(run.run_id)
        ]
        changes.sort(key=lambda change: (change.created_at, str(change.file_change_id)))
        return [FileChangeResponse.from_change(change) for change in changes]

    @app.post(
        "/api/v1/file-changes/{change_id}/undo",
        response_model=FileChangeResponse,
        dependencies=[Depends(authenticate)],
    )
    async def undo_file_change(
        change_id: str,
        request: UndoFileChangeRequest,
    ) -> FileChangeResponse:
        if file_changes is None or revert_file_change is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="file changes are unavailable",
            )
        stored_change = await file_changes.get(FileChangeId(change_id))
        if stored_change is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file change not found",
            )
        await get_local_run(stored_change.run_id)
        try:
            reverted = await revert_file_change(
                stored_change.file_change_id,
                Path(request.path),
            )
        except FileChangeNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="file change not found",
            ) from error
        except (FileChangeConflictError, ValueError) as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            ) from error
        return FileChangeResponse.from_change(reverted)

    if tavily_settings is not None:

        @app.get(
            "/api/v1/settings/tavily",
            response_model=TavilySettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_tavily_settings() -> TavilySettingsResponse:
            tavily_status = await tavily_settings.get_status()
            return TavilySettingsResponse.from_status(tavily_status)

        @app.put(
            "/api/v1/settings/tavily",
            response_model=TavilySettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_tavily_settings(
            request: UpdateTavilySettingsRequest,
        ) -> TavilySettingsResponse:
            try:
                tavily_status = await tavily_settings.enable(api_key=request.api_key)
            except TavilyApiKeyMissingError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="tavily api key is not saved",
                ) from error

            return TavilySettingsResponse.from_status(tavily_status)

        @app.post(
            "/api/v1/settings/tavily/disable",
            response_model=TavilySettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def disable_tavily_settings() -> TavilySettingsResponse:
            tavily_status = await tavily_settings.disable()
            return TavilySettingsResponse.from_status(tavily_status)

        @app.delete(
            "/api/v1/settings/tavily",
            response_model=TavilySettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def delete_tavily_settings() -> TavilySettingsResponse:
            tavily_status = await tavily_settings.delete()
            return TavilySettingsResponse.from_status(tavily_status)

    if model_settings is not None:

        @app.get(
            "/api/v1/settings/model",
            response_model=ModelSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_model_settings() -> ModelSettingsResponse:
            return ModelSettingsResponse.from_status(await model_settings.get_status())

        @app.put(
            "/api/v1/settings/model",
            response_model=ModelSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_model_settings(
            request: UpdateModelSettingsRequest,
        ) -> ModelSettingsResponse:
            try:
                saved_status = await model_settings.save(
                    location=request.location,
                    model=request.model,
                    base_url=str(request.base_url),
                    api_key=request.api_key,
                )
            except ModelApiKeyMissingError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="model api key is not saved",
                ) from error
            except ValidationError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="local model base URL must use localhost or a loopback address",
                ) from error

            return ModelSettingsResponse.from_status(saved_status)

        @app.delete(
            "/api/v1/settings/model",
            response_model=ModelSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def delete_model_settings() -> ModelSettingsResponse:
            return ModelSettingsResponse.from_status(await model_settings.delete())

    if agent_settings is not None:

        @app.get(
            "/api/v1/agent-settings",
            response_model=AgentSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_agent_settings() -> AgentSettingsResponse:
            try:
                settings = agent_settings.get()
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="agent settings are invalid",
                ) from error
            return AgentSettingsResponse.from_settings(settings)

        @app.put(
            "/api/v1/agent-settings",
            response_model=AgentSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_agent_settings(
            request: UpdateAgentSettingsRequest,
        ) -> AgentSettingsResponse:
            try:
                saved = agent_settings.save(AgentSettings(max_steps=request.max_steps))
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="agent settings are invalid",
                ) from error
            return AgentSettingsResponse.from_settings(saved)

    if storage_settings is not None and file_change_snapshots is not None:

        @app.get(
            "/api/v1/settings/storage",
            response_model=StorageSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_storage_settings() -> StorageSettingsResponse:
            try:
                settings = storage_settings.get()
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="storage settings are invalid",
                ) from error
            usage_bytes, count = file_change_snapshots.get_usage()
            return StorageSettingsResponse(
                snapshot_retention_days=settings.snapshot_retention_days,
                usage_bytes=usage_bytes,
                snapshot_count=count,
            )

        @app.put(
            "/api/v1/settings/storage",
            response_model=StorageSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_storage_settings(
            request: UpdateStorageSettingsRequest,
        ) -> StorageSettingsResponse:
            try:
                saved = storage_settings.save(
                    StorageSettings(
                        snapshot_retention_days=request.snapshot_retention_days
                    )
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="storage settings are invalid",
                ) from error
            usage_bytes, count = file_change_snapshots.get_usage()
            return StorageSettingsResponse(
                snapshot_retention_days=saved.snapshot_retention_days,
                usage_bytes=usage_bytes,
                snapshot_count=count,
            )

        @app.post(
            "/api/v1/settings/storage/clear",
            response_model=ClearStorageResponse,
            dependencies=[Depends(authenticate)],
        )
        async def clear_storage_snapshots() -> ClearStorageResponse:
            freed, count = file_change_snapshots.clear()
            return ClearStorageResponse(freed_bytes=freed, deleted_count=count)

    if workspace_settings is not None:

        @app.get(
            "/api/v1/conversations/{conversation_id}/file-access",
            response_model=WorkspaceSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_workspace_settings(
            conversation_id: str,
        ) -> WorkspaceSettingsResponse:
            conversation = await get_local_conversation(
                ConversationId(conversation_id), kind="chat"
            )
            return WorkspaceSettingsResponse.from_status(
                await workspace_settings.get_status(conversation.conversation_id)
            )

        @app.put(
            "/api/v1/conversations/{conversation_id}/file-access",
            response_model=WorkspaceSettingsResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_workspace_settings(
            conversation_id: str,
            request: UpdateWorkspaceSettingsRequest,
        ) -> WorkspaceSettingsResponse:
            conversation = await get_local_conversation(
                ConversationId(conversation_id), kind="chat"
            )
            try:
                saved_status = await workspace_settings.save(
                    conversation_id=conversation.conversation_id,
                    additional_roots=tuple(
                        Path(root) for root in request.additional_roots
                    ),
                    additional_files=tuple(
                        Path(file_path) for file_path in request.additional_files
                    ),
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="workspace paths are invalid",
                ) from error
            return WorkspaceSettingsResponse.from_status(saved_status)

    if automations is not None:

        async def get_local_automation(automation_id: str) -> Automation:
            automation = await automations.get(AutomationId(automation_id))
            if automation is None or automation.user_id != _LOCAL_USER_ID:
                raise HTTPException(status_code=404, detail="automation not found")
            return automation

        @app.get(
            "/api/v1/automations",
            response_model=list[AutomationResponse],
            dependencies=[Depends(authenticate)],
        )
        async def list_automations() -> list[AutomationResponse]:
            return [
                AutomationResponse.from_automation(value)
                for value in await automations.list_for_user(_LOCAL_USER_ID)
            ]

        @app.post(
            "/api/v1/automations",
            response_model=AutomationResponse,
            status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(authenticate)],
        )
        async def create_automation(
            request: CreateAutomationRequest,
        ) -> AutomationResponse:
            created_at = current_time()
            try:
                local_time = time.fromisoformat(request.trigger.local_time)
                automation = Automation(
                    create_automation_id(),
                    _LOCAL_USER_ID,
                    request.name,
                    request.plan_summary,
                    tuple(request.allowed_capabilities),
                    AutomationStatus.DRAFT,
                    created_at,
                    created_at,
                )
                trigger = AutomationTrigger(
                    create_automation_trigger_id(),
                    automation.automation_id,
                    AutomationTriggerKind(request.trigger.kind),
                    request.trigger.timezone,
                    local_time,
                    request.trigger.weekday,
                    request.trigger.next_run_at,
                    True,
                    created_at,
                    created_at,
                )
                if trigger.next_run_at is None:
                    next_run_at = next_run_after(trigger, created_at)
                    if next_run_at is None:
                        raise ValueError("once triggers require next_run_at")
                    trigger = replace(trigger, next_run_at=next_run_at)
            except ValueError as error:
                raise HTTPException(
                    status_code=422, detail="automation input is invalid"
                ) from error
            await automations.save_with_trigger(automation, trigger)
            return AutomationResponse.from_automation(automation)

        @app.get(
            "/api/v1/automations/{automation_id}",
            response_model=AutomationResponse,
            dependencies=[Depends(authenticate)],
        )
        async def get_automation(automation_id: str) -> AutomationResponse:
            return AutomationResponse.from_automation(
                await get_local_automation(automation_id)
            )

        @app.delete(
            "/api/v1/automations/{automation_id}",
            status_code=status.HTTP_204_NO_CONTENT,
            dependencies=[Depends(authenticate)],
        )
        async def delete_automation(automation_id: str) -> Response:
            await get_local_automation(automation_id)
            await automations.delete(AutomationId(automation_id))
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        @app.post(
            "/api/v1/automations/{automation_id}/run-now",
            response_model=AutomationExecutionResponse,
            status_code=status.HTTP_202_ACCEPTED,
            dependencies=[Depends(authenticate)],
        )
        async def run_automation_now(automation_id: str) -> AutomationExecutionResponse:
            stored = await get_local_automation(automation_id)
            if run_automation_now_action is None:
                raise HTTPException(
                    status_code=503, detail="automation runner unavailable"
                )
            try:
                execution = await run_automation_now_action(stored.automation_id)
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return AutomationExecutionResponse.from_execution(execution)

        @app.put(
            "/api/v1/automations/{automation_id}",
            response_model=AutomationResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_automation(
            automation_id: str, request: UpdateAutomationRequest
        ) -> AutomationResponse:
            stored = await get_local_automation(automation_id)
            triggers = await automations.list_triggers(stored.automation_id)
            if len(triggers) != 1:
                raise HTTPException(
                    status_code=409,
                    detail="automation must have exactly one editable trigger",
                )
            updated_at = current_time()
            try:
                local_time = time.fromisoformat(request.trigger.local_time)
                automation = replace(
                    stored,
                    name=request.name,
                    plan_summary=request.plan_summary,
                    allowed_capabilities=tuple(request.allowed_capabilities),
                    updated_at=updated_at,
                )
                trigger = AutomationTrigger(
                    triggers[0].automation_trigger_id,
                    stored.automation_id,
                    AutomationTriggerKind(request.trigger.kind),
                    request.trigger.timezone,
                    local_time,
                    request.trigger.weekday,
                    request.trigger.next_run_at,
                    triggers[0].enabled,
                    triggers[0].created_at,
                    updated_at,
                )
                if trigger.next_run_at is None:
                    next_run_at = next_run_after(trigger, updated_at)
                    if next_run_at is None:
                        raise ValueError("once triggers require next_run_at")
                    trigger = replace(trigger, next_run_at=next_run_at)
            except ValueError as error:
                raise HTTPException(
                    status_code=422, detail="automation input is invalid"
                ) from error
            await automations.save_with_trigger(automation, trigger)
            return AutomationResponse.from_automation(automation)

        @app.put(
            "/api/v1/automations/{automation_id}/status",
            response_model=AutomationResponse,
            dependencies=[Depends(authenticate)],
        )
        async def update_automation_status(
            automation_id: str, request: UpdateAutomationStatusRequest
        ) -> AutomationResponse:
            stored = await get_local_automation(automation_id)
            saved = replace(
                stored,
                status=AutomationStatus(request.status),
                updated_at=current_time(),
            )
            await automations.save(saved)
            return AutomationResponse.from_automation(saved)

        @app.get(
            "/api/v1/automations/{automation_id}/triggers",
            response_model=list[AutomationTriggerResponse],
            dependencies=[Depends(authenticate)],
        )
        async def list_automation_triggers(
            automation_id: str,
        ) -> list[AutomationTriggerResponse]:
            stored = await get_local_automation(automation_id)
            return [
                AutomationTriggerResponse.from_trigger(value)
                for value in await automations.list_triggers(stored.automation_id)
            ]

        @app.get(
            "/api/v1/automations/{automation_id}/executions",
            response_model=list[AutomationExecutionResponse],
            dependencies=[Depends(authenticate)],
        )
        async def list_automation_executions(
            automation_id: str,
        ) -> list[AutomationExecutionResponse]:
            stored = await get_local_automation(automation_id)
            return [
                AutomationExecutionResponse.from_execution(value)
                for value in await automations.list_executions(stored.automation_id)
            ]

        @app.get(
            "/api/v1/automations/{automation_id}/executions/{execution_id}/messages",
            response_model=list[MessageResponse],
            dependencies=[Depends(authenticate)],
        )
        async def get_automation_execution_messages(
            automation_id: str,
            execution_id: str,
        ) -> list[MessageResponse]:
            stored = await get_local_automation(automation_id)
            execution = await automations.get_execution(
                AutomationExecutionId(execution_id)
            )
            if execution is None or execution.automation_id != stored.automation_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="automation execution not found",
                )
            if execution.run_id is None:
                return []
            run = await runs.get(execution.run_id)
            if run is None:
                return []
            stored_messages = await conversations.list_messages(run.conversation_id)
            return [
                MessageResponse.from_message(message) for message in stored_messages
            ]

    return app


def _new_conversation_id() -> ConversationId:
    return ConversationId(f"conv_{uuid4().hex}")


def _new_automation_id() -> AutomationId:
    return AutomationId(f"automation_{uuid4().hex}")


def _new_automation_trigger_id() -> AutomationTriggerId:
    return AutomationTriggerId(f"automation_trigger_{uuid4().hex}")


def _now() -> datetime:
    return datetime.now(UTC)
