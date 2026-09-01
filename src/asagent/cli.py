import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from asagent.agent.cancellation import RunCancellationToken
from asagent.agent.loop import AgentLoop
from asagent.agent.persistent_runtime import PersistentAgentRuntime
from asagent.agent.run_dispatcher import InProcessRunDispatcher
from asagent.agent.run_submission import RunSubmissionService, SubmittedRun
from asagent.api.app import create_app
from asagent.api.bootstrap import read_local_api_bootstrap
from asagent.api.server import READY_PREFIX, LocalApiServer
from asagent.automation.browser.browser_service import AutomationBrowserService
from asagent.automation.browser.tools import (
    AutomationBrowserClickTool,
    AutomationBrowserCloseTool,
    AutomationBrowserFillTool,
    AutomationBrowserNavigateTool,
    AutomationBrowserReadPageTool,
    AutomationBrowserSelectTool,
    AutomationBrowserSnapshotTool,
    AutomationBrowserWaitTool,
)
from asagent.automation.drafts import AutomationDraftContextStore
from asagent.automation.scheduler import (
    AutomationExecutionContextStore,
    AutomationRunSubmissionService,
    AutomationScheduler,
)
from asagent.bootstrap.agent_settings import AgentSettingsStore
from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.bootstrap.credential_secret_provider import CredentialStoreSecretProvider
from asagent.bootstrap.environment_secret_provider import (
    EnvironmentSecretProvider,
)
from asagent.bootstrap.keychain_credential_store import (
    MacOSKeychainCredentialStore,
)
from asagent.bootstrap.model_settings import (
    MODEL_CONNECTION_ID,
    MODEL_PROFILE_NAME,
    MODEL_SECRET_ID,
    ModelSettings,
)
from asagent.bootstrap.provider_factory import create_model_provider
from asagent.bootstrap.storage_settings import StorageSettingsStore
from asagent.bootstrap.tavily_settings import TavilySettings
from asagent.chat.service import ChatService
from asagent.core.connection import CredentialStore
from asagent.core.conversation import Conversation
from asagent.core.event_publisher import EventPublisher
from asagent.core.file_change import FileChange
from asagent.core.ids import (
    ApprovalId,
    ConnectionId,
    ConversationId,
    EventId,
    FileChangeId,
    MessageId,
    RunId,
    ToolCallId,
    UserId,
)
from asagent.core.repositories import ConversationRepository
from asagent.core.run_event import RunEvent
from asagent.core.run_status import RunStatus
from asagent.core.tool_call_recorder import ToolCallRecorder
from asagent.knowledge import (
    KnowledgeContextAugmenter,
    KnowledgeIndexer,
    KnowledgeRetriever,
    LocalMiniLMEmbedder,
)
from asagent.models.config import ProviderProfiles
from asagent.models.contracts import (
    ModelEvent,
    ModelMessage,
    ModelMessageRole,
    ModelRequest,
    ModelResponse,
    ModelToolCall,
)
from asagent.models.errors import ProviderConfigurationError
from asagent.models.profile_loader import load_provider_profiles
from asagent.models.provider import ModelProvider
from asagent.models.secrets import SecretProvider
from asagent.models.tool_names import openai_compatible_tool_name
from asagent.paths import AppPaths
from asagent.storage.event_publisher import RepositoryEventPublisher
from asagent.storage.file_change_snapshots import FileChangeSnapshotStore
from asagent.storage.qdrant import KnowledgeVectorStore
from asagent.storage.reversible_files import (
    FileChangeNotFoundError,
    ReversibleFileService,
)
from asagent.storage.sqlite.automation_repository import SqliteAutomationRepository
from asagent.storage.sqlite.connection_repository import (
    SqliteConnectionRepository,
)
from asagent.storage.sqlite.conversation_file_scope_repository import (
    SqliteConversationFileScopeRepository,
)
from asagent.storage.sqlite.conversation_repository import (
    SqliteConversationRepository,
)
from asagent.storage.sqlite.database import upgrade_sqlite_database
from asagent.storage.sqlite.file_change_repository import (
    SqliteFileChangeRepository,
)
from asagent.storage.sqlite.knowledge_repository import (
    SqliteKnowledgeRepository,
)
from asagent.storage.sqlite.run_finisher import SqliteRunFinisher
from asagent.storage.sqlite.run_repository import SqliteRunRepository
from asagent.storage.sqlite.run_starter import SqliteRunStarter
from asagent.storage.tool_call_recorder import RepositoryToolCallRecorder
from asagent.tools.approval import PendingToolApprovalPolicy, ToolApprovalPolicy
from asagent.tools.automation_save import AutomationPlanUpdateTool, AutomationSaveTool
from asagent.tools.browser_click import BrowserClickTool
from asagent.tools.browser_fill import BrowserFillTool
from asagent.tools.browser_inspect_interactive import BrowserInspectInteractiveTool
from asagent.tools.browser_navigate import BrowserNavigateTool
from asagent.tools.browser_read_current_page import BrowserReadCurrentPageTool
from asagent.tools.browser_read_current_pdf import BrowserReadCurrentPdfTool
from asagent.tools.browser_run_bindings import BrowserRunBindings
from asagent.tools.browser_select import BrowserSelectTool
from asagent.tools.browser_wait import BrowserWaitTool
from asagent.tools.builtin.calculator import CalculatorTool
from asagent.tools.builtin.current_time import CurrentTimeTool
from asagent.tools.builtin.document_extract_text import DocumentExtractTextTool
from asagent.tools.builtin.echo import EchoTool
from asagent.tools.builtin.filesystem_changes import (
    FilesystemCreateFileTool,
    FilesystemDeleteFileTool,
    FilesystemReplaceFileTool,
)
from asagent.tools.builtin.filesystem_list import FilesystemListTool
from asagent.tools.builtin.filesystem_read_file import FilesystemReadFileTool
from asagent.tools.builtin.filesystem_search_files import FilesystemSearchFilesTool
from asagent.tools.executor import ToolExecutor
from asagent.tools.mcp_config import load_mcp_server_configs
from asagent.tools.mcp_manager import McpServerManager
from asagent.tools.registry import ToolRegistry
from asagent.tools.snapshot import ToolSnapshot
from asagent.workspace.resolver import WorkspaceResolver
from asagent.workspace.settings import ConversationWorkspaceSettings

_BUILTIN_TOOL_PERMISSIONS = frozenset({"tool.execute"})
_FILESYSTEM_READ_PERMISSIONS = frozenset({"filesystem.read"})
_FILESYSTEM_WRITE_PERMISSIONS = frozenset({"filesystem.write"})
_BROWSER_READ_PERMISSIONS = frozenset({"browser.read"})
_BROWSER_NAVIGATE_PERMISSIONS = frozenset({"browser.navigate"})
_BROWSER_INSPECT_PERMISSIONS = frozenset({"browser.inspect"})
_BROWSER_CLICK_PERMISSIONS = frozenset({"browser.click"})
_BROWSER_FILL_PERMISSIONS = frozenset({"browser.fill"})
_BROWSER_SELECT_PERMISSIONS = frozenset({"browser.select"})
_BROWSER_WAIT_PERMISSIONS = frozenset({"browser.wait"})
_BROWSER_TOOL_PERMISSIONS = (
    _BROWSER_READ_PERMISSIONS
    | _BROWSER_NAVIGATE_PERMISSIONS
    | _BROWSER_INSPECT_PERMISSIONS
    | _BROWSER_CLICK_PERMISSIONS
    | _BROWSER_WAIT_PERMISSIONS
)
_MCP_SUBPROCESS_ENVIRONMENT_NAMES = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "SHELL",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
)


class _EchoModelProvider:
    async def complete(self, request: ModelRequest) -> ModelResponse:
        content = next(
            (
                message.content
                for message in reversed(request.messages)
                if message.role is ModelMessageRole.USER
            ),
            "",
        )
        return ModelResponse(text=f"Echo: {content}", tool_calls=())

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text is not None:
            yield ModelEvent(event_type="model.delta", text_delta=response.text)


class DevelopmentToolModelProvider:
    """A deterministic offline Provider for manually exercising the Agent Loop."""

    def __init__(self, tool_snapshot: ToolSnapshot) -> None:
        self._tool_snapshot = tool_snapshot

    async def complete(self, request: ModelRequest) -> ModelResponse:
        last_message = request.messages[-1]
        if last_message.role is ModelMessageRole.TOOL:
            return ModelResponse(
                text=f"Tool result: {last_message.content}",
                tool_calls=(),
            )

        if last_message.role is not ModelMessageRole.USER:
            raise RuntimeError("development agent expected a user or tool message")

        content = last_message.content or ""
        normalized = content.strip().lower()
        if normalized.startswith("calculate "):
            tool_id = "builtin.calculator"
            arguments: dict[str, object] = {
                "expression": content.strip()[len("calculate ") :],
            }
        elif normalized in {"time", "current time", "what time is it?"}:
            tool_id = "builtin.current_time"
            arguments = {}
        else:
            tool_id = "builtin.echo"
            arguments = {"text": content}

        return ModelResponse(
            text=None,
            tool_calls=(
                ModelToolCall(
                    call_id="development_tool_call",
                    name=self._tool_snapshot.provider_name_for(tool_id),
                    arguments=arguments,
                ),
            ),
        )

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        del request
        raise RuntimeError("development agent does not support streaming")


class ConsoleEventPublisher:
    def __init__(self, write_line: Callable[[str], None]) -> None:
        self._write_line = write_line

    async def publish(self, event: RunEvent) -> None:
        data = json.dumps(dict(event.data), ensure_ascii=False, sort_keys=True)
        self._write_line(f"[event {event.sequence}] {event.event_type} {data}")


def _register_builtin_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    return registry


async def _registry_for_conversation(
    *,
    base_registry: ToolRegistry,
    workspace_settings: ConversationWorkspaceSettings,
    run_id: RunId,
    conversation_id: ConversationId,
    conversations: ConversationRepository,
    automations: SqliteAutomationRepository | None = None,
    automation_drafts: AutomationDraftContextStore | None = None,
    automation_execution_contexts: AutomationExecutionContextStore | None = None,
    automation_browser_service: AutomationBrowserService | None = None,
    file_changes: SqliteFileChangeRepository | None = None,
    file_change_snapshots: FileChangeSnapshotStore | None = None,
) -> ToolRegistry:
    """Build an isolated Tool Registry for the Run's Conversation kind."""

    conversation = await conversations.get(conversation_id)
    if conversation is None:
        raise ValueError("conversation not found")
    if conversation.kind == "automation_draft":
        if (
            automations is None
            or automation_drafts is None
            or not automation_drafts.contains(conversation_id)
        ):
            raise RuntimeError("automation draft context is unavailable")
        registry = ToolRegistry()
        registry.register(CurrentTimeTool(now))
        registry.register(
            AutomationSaveTool(
                automations=automations,
                drafts=automation_drafts,
                conversation_id=conversation_id,
                user_id=conversation.user_id,
                now=now,
            )
        )
        return registry

    registry = (
        base_registry.copy()
        if conversation.kind == "chat"
        else _register_builtin_tools()
    )
    if conversation.kind == "knowledge":
        return registry

    status = await workspace_settings.get_status(conversation_id)
    resolver = WorkspaceResolver(
        workspace_root=status.workspace_root,
        additional_roots=status.additional_roots,
        additional_files=status.additional_files,
    )
    if (
        conversation.kind == "automation_execution"
        and automations is not None
        and automation_execution_contexts is not None
    ):
        target_automation_id = automation_execution_contexts.target(conversation_id)
        if target_automation_id is not None:
            registry.register(
                AutomationPlanUpdateTool(
                    automations=automations,
                    automation_id=target_automation_id,
                    user_id=conversation.user_id,
                    now=now,
                )
            )
    registry.register(FilesystemListTool(resolver))
    registry.register(FilesystemReadFileTool(resolver))
    registry.register(DocumentExtractTextTool(resolver))
    registry.register(FilesystemSearchFilesTool(resolver))
    if (
        conversation.kind == "automation_execution"
        and automation_browser_service is not None
    ):
        registry.register(AutomationBrowserNavigateTool(automation_browser_service))
        registry.register(AutomationBrowserSnapshotTool(automation_browser_service))
        registry.register(AutomationBrowserClickTool(automation_browser_service))
        registry.register(AutomationBrowserFillTool(automation_browser_service))
        registry.register(AutomationBrowserSelectTool(automation_browser_service))
        registry.register(AutomationBrowserWaitTool(automation_browser_service))
        registry.register(AutomationBrowserReadPageTool(automation_browser_service))
        registry.register(AutomationBrowserCloseTool(automation_browser_service))
    if file_changes is not None and file_change_snapshots is not None:
        service = ReversibleFileService(
            resolver,
            file_changes,
            file_change_snapshots,
            new_file_change_id,
            now,
        )
        registry.register(FilesystemCreateFileTool(service, run_id))
        registry.register(FilesystemReplaceFileTool(service, run_id))
        registry.register(FilesystemDeleteFileTool(service, run_id))
    return registry


async def _register_browser_tools(
    *,
    registry: ToolRegistry,
    conversations: ConversationRepository,
    conversation_id: ConversationId,
    run_id: RunId,
    browser_run_bindings: BrowserRunBindings | None,
    browser_page_client: BrowserPageBridgeClient | None,
) -> frozenset[str]:
    """Register visible page tools only for a bound Browser Conversation Run."""

    tab_id = None if browser_run_bindings is None else browser_run_bindings.take(run_id)
    if tab_id is None or browser_page_client is None or browser_run_bindings is None:
        return frozenset()

    conversation = await conversations.get(conversation_id)
    if conversation is None or conversation.kind != "browser":
        return frozenset()

    registry.register(
        BrowserReadCurrentPageTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserNavigateTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserInspectInteractiveTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserClickTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserFillTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserSelectTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserWaitTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    registry.register(
        BrowserReadCurrentPdfTool(
            client=browser_page_client,
            tab_id=tab_id,
        ),
    )
    return (
        _BROWSER_TOOL_PERMISSIONS
        | _BROWSER_FILL_PERMISSIONS
        | _BROWSER_SELECT_PERMISSIONS
    )


async def _system_prompt_for_conversation(
    *,
    workspace_settings: ConversationWorkspaceSettings,
    conversations: ConversationRepository,
    conversation_id: ConversationId,
    automations: SqliteAutomationRepository | None = None,
    automation_drafts: AutomationDraftContextStore | None = None,
    knowledge_augmenter: KnowledgeContextAugmenter | None = None,
    user_query: str = "",
    run_id: RunId | None = None,
) -> str:
    """Add the visible-browser or knowledge operating contract to conversations."""

    conversation = await conversations.get(conversation_id)
    workspace_context = (
        ""
        if conversation is not None and conversation.kind == "knowledge"
        else await workspace_settings.model_context(conversation_id)
    )
    if conversation is not None and conversation.kind == "automation_draft":
        target = (
            None
            if automation_drafts is None
            else automation_drafts.target(conversation_id)
        )
        target_context = "Create a new automation."
        if target is not None and automations is not None:
            stored = await automations.get(target)
            if stored is not None:
                triggers = await automations.list_triggers(target)
                trigger = triggers[0] if len(triggers) == 1 else None
                target_context = (
                    f"Update automation {target}. Current name: {stored.name}. "
                    f"Current plan: {stored.plan_summary}. "
                    f"Current schedule: {trigger.kind.value if trigger else 'unknown'} "
                    f"at {trigger.local_time.isoformat() if trigger else 'unknown'} "
                    f"in {trigger.timezone if trigger else 'unknown'}."
                )
        return (
            "You are in a dedicated automation planning conversation. Help the user express "
            "the task and schedule in natural language. Before using any tool, check that the name, "
            "complete repeatable instructions, frequency, local time, and timezone are all known. "
            "If any required detail is missing, do not call any tool and do not execute, inspect, "
            "or test the task. Your entire response must be one concise question that asks only for "
            "the missing information. When the name, complete repeatable instructions, frequency, local "
            "time, and IANA timezone are unambiguous, call automation.save_draft. The user's "
            f"current local timezone is {automation_drafts.timezone(conversation_id) if automation_drafts else 'UTC'}; "
            "use it unless the user specifies another timezone. For weekly "
            "schedules also determine weekday; for once schedules determine a timezone-aware "
            "future instant. Automation planning never executes, inspects, or tests the task itself. "
            "After saving, the user can use Run now from the task detail page to test the real task. "
            "New automations are saved as Draft and must be enabled separately. "
            f"{target_context}"
        )

    base_prompt = workspace_context
    if conversation is not None and conversation.kind == "browser":
        browser_context = (
            "You are operating the user's visible browser tab. Use the browser "
            "tools listed for this run to perform requested page operations. "
            "If the current page is a PDF document, use browser.read_current_pdf to extract its text. "
            "Take a browser.take_snapshot before acting on unfamiliar page elements, "
            "then use only its returned refs. Do not claim browser capability is "
            "unavailable without taking a snapshot first. Browser tools act only "
            "on the visible tab and cannot read credentials; ask the user to enter "
            "passwords directly."
        )
        base_prompt = "\n\n".join(
            part for part in (workspace_context, browser_context) if part
        )

    if knowledge_augmenter is not None:
        augmented = await knowledge_augmenter.augment_system_prompt(
            conversation_id=conversation_id,
            base_system_prompt=base_prompt,
            user_query=user_query,
            run_id=run_id,
        )
        return augmented.system_prompt

    return base_prompt


def _filesystem_permissions(
    *,
    file_changes: SqliteFileChangeRepository | None,
    file_change_snapshots: FileChangeSnapshotStore | None,
) -> frozenset[str]:
    permissions = _FILESYSTEM_READ_PERMISSIONS
    if file_changes is not None and file_change_snapshots is not None:
        permissions = permissions | _FILESYSTEM_WRITE_PERMISSIONS
    return permissions


_MACOS_STANDARD_TOOL_DIRS: tuple[str, ...] = (
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
)
_MACOS_SYSTEM_BIN_DIRS: tuple[str, ...] = (
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
)


def _normalize_subprocess_path(
    current_path: str | None,
    *,
    platform_name: str | None = None,
    user_home: Path | None = None,
) -> str:
    current = platform_name if platform_name is not None else sys.platform
    parts: list[str] = [
        p.strip() for p in (current_path or "").split(os.pathsep) if p.strip()
    ]
    seen = set(parts)

    if current == "darwin":
        tool_dirs = [d for d in _MACOS_STANDARD_TOOL_DIRS if d not in seen]
        home = user_home if user_home is not None else Path.home()
        user_dirs = [
            str(home / sub)
            for sub in (".cargo/bin", ".local/bin")
            if str(home / sub) not in seen
        ]
        nvm_node_dirs = _nvm_node_bin_directories(home, seen=seen)
        prepend_dirs = tool_dirs + nvm_node_dirs + user_dirs
        parts = prepend_dirs + parts
        seen.update(prepend_dirs)

        for sys_dir in _MACOS_SYSTEM_BIN_DIRS:
            if sys_dir not in seen:
                parts.append(sys_dir)
                seen.add(sys_dir)

    return os.pathsep.join(parts)


def _nvm_node_bin_directories(
    user_home: Path,
    *,
    seen: set[str],
) -> list[str]:
    """Return installed NVM Node bin directories, newest version first."""

    versions_dir = user_home / ".nvm" / "versions" / "node"
    if any(
        Path(existing).name == "bin" and Path(existing).parent.parent == versions_dir
        for existing in seen
    ):
        return []

    try:
        version_dirs = tuple(versions_dir.iterdir())
    except OSError:
        return []

    candidates: list[tuple[tuple[int, int, int], str]] = []
    for version_dir in version_dirs:
        version = version_dir.name.removeprefix("v").split(".")
        if len(version) != 3 or any(not part.isdigit() for part in version):
            continue

        bin_dir = str(version_dir / "bin")
        if bin_dir in seen or not Path(bin_dir).is_dir():
            continue
        version_key = (int(version[0]), int(version[1]), int(version[2]))
        candidates.append((version_key, bin_dir))

    candidates.sort(reverse=True)
    return [bin_dir for _, bin_dir in candidates]


def _mcp_subprocess_environment(
    environment: Mapping[str, str],
    *,
    platform_name: str | None = None,
) -> dict[str, str]:
    """Return the intentionally small environment inherited by MCP children."""

    home_value = environment.get("HOME") or str(Path.home())
    user_home = Path(home_value)
    env: dict[str, str] = {}
    for name in _MCP_SUBPROCESS_ENVIRONMENT_NAMES:
        value = environment.get(name)
        if name == "PATH":
            env["PATH"] = _normalize_subprocess_path(
                value,
                platform_name=platform_name,
                user_home=user_home,
            )
        elif name == "HOME":
            env["HOME"] = home_value
        elif value is not None:
            env[name] = value

    return env


async def _start_configured_mcp_servers(
    *,
    config_dir: Path,
    environment: Mapping[str, str],
    credential_store: CredentialStore | None = None,
) -> tuple[ToolRegistry, McpServerManager, bool]:
    configs = load_mcp_server_configs(config_dir)
    registry = _register_builtin_tools()

    if any(config.requires_credential for config in configs.servers.values()):
        credential_store = credential_store or MacOSKeychainCredentialStore()

    manager = McpServerManager(
        configs=configs,
        registry=registry,
        environment=_mcp_subprocess_environment(environment),
        credential_store=credential_store,
    )
    await manager.start()
    return registry, manager, manager.has_active_servers


def build_agent_loop(
    *,
    model: ModelProvider,
    event_publisher: EventPublisher,
    tool_call_recorder: ToolCallRecorder | None = None,
    approval_policy: ToolApprovalPolicy | None = None,
    registry: ToolRegistry | None = None,
    granted_permissions: frozenset[str] = _BUILTIN_TOOL_PERMISSIONS,
    max_steps: int = 20,
    max_calls_per_tool_input: int | None = None,
    max_tool_calls_per_model_response: int | None = None,
) -> AgentLoop:
    tool_registry = registry if registry is not None else _register_builtin_tools()
    snapshot = ToolSnapshot.from_definitions(
        tool_registry.definitions(),
        provider_name_for=openai_compatible_tool_name,
    )
    return AgentLoop(
        model=model,
        executor=ToolExecutor(
            tool_registry,
            granted_permissions=granted_permissions,
            approval_policy=approval_policy,
        ),
        tool_snapshot=snapshot,
        max_steps=max_steps,
        max_calls_per_tool_input=max_calls_per_tool_input,
        max_tool_calls_per_model_response=max_tool_calls_per_model_response,
        event_publisher=event_publisher,
        event_id_factory=new_event_id,
        clock=now,
        tool_call_recorder=tool_call_recorder,
        tool_call_id_factory=(
            new_tool_call_id if tool_call_recorder is not None else None
        ),
        approval_id_factory=new_approval_id,
    )


def build_development_agent_loop(
    *,
    event_publisher: EventPublisher,
    tool_call_recorder: ToolCallRecorder | None = None,
    approval_policy: ToolApprovalPolicy | None = None,
    registry: ToolRegistry | None = None,
    granted_permissions: frozenset[str] = _BUILTIN_TOOL_PERMISSIONS,
    max_steps: int = 20,
    max_calls_per_tool_input: int | None = None,
    max_tool_calls_per_model_response: int | None = None,
) -> AgentLoop:
    tool_registry = registry if registry is not None else _register_builtin_tools()
    snapshot = ToolSnapshot.from_definitions(
        tool_registry.definitions(),
        provider_name_for=openai_compatible_tool_name,
    )
    return AgentLoop(
        model=DevelopmentToolModelProvider(snapshot),
        executor=ToolExecutor(
            tool_registry,
            granted_permissions=granted_permissions,
            approval_policy=approval_policy,
        ),
        tool_snapshot=snapshot,
        max_steps=max_steps,
        max_calls_per_tool_input=max_calls_per_tool_input,
        max_tool_calls_per_model_response=max_tool_calls_per_model_response,
        event_publisher=event_publisher,
        event_id_factory=new_event_id,
        clock=now,
        tool_call_recorder=tool_call_recorder,
        tool_call_id_factory=new_tool_call_id,
        approval_id_factory=new_approval_id,
    )


async def run_agent_chat(
    *,
    agent_loop: AgentLoop,
    conversation_id: ConversationId,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
    new_run_id: Callable[[], RunId],
) -> None:
    history: list[ModelMessage] = []
    write_line("asAgent development agent. Type 'exit' to quit.")

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        history.append(
            ModelMessage(role=ModelMessageRole.USER, content=content),
        )
        try:
            result = await agent_loop.run(
                model_name=model_name,
                system_prompt=system_prompt,
                messages=tuple(history),
                run_id=new_run_id(),
                conversation_id=conversation_id,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        history = list(result.messages)
        if result.status is RunStatus.COMPLETED and result.text is not None:
            write_line(f"asAgent: {result.text}")
        elif result.error is not None:
            write_line(f"Error: {result.error}")
        else:
            write_line(f"Run ended: {result.status.value}")


async def run_chat(
    *,
    chat_service: ChatService,
    conversation: Conversation,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
) -> None:
    write_line("asAgent development chat. Type 'exit' to quit.")

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        try:
            reply = await chat_service.send(
                conversation=conversation,
                content=content,
                model_name=model_name,
                system_prompt=system_prompt,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        write_line(f"asAgent: {reply.content}")


def now() -> datetime:
    return datetime.now(UTC)


def new_conversation_id() -> ConversationId:
    return ConversationId(f"conv_{uuid4().hex}")


def new_event_id() -> EventId:
    return EventId(f"evt_{uuid4().hex}")


def new_message_id() -> MessageId:
    return MessageId(f"msg_{uuid4().hex}")


def new_run_id() -> RunId:
    return RunId(f"run_{uuid4().hex}")


def new_tool_call_id() -> ToolCallId:
    return ToolCallId(f"tool_{uuid4().hex}")


def new_approval_id() -> ApprovalId:
    return ApprovalId(f"approval_{uuid4().hex}")


def new_file_change_id() -> FileChangeId:
    return FileChangeId(f"change_{uuid4().hex}")


def _application_resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS).joinpath(*parts)  # type: ignore[attr-defined]

    return Path(__file__).resolve().parents[2].joinpath(*parts)


def _alembic_config_path() -> Path:
    return _application_resource_path("alembic.ini")


def build_persistent_agent_runtime(
    *,
    model: ModelProvider,
    conversations: SqliteConversationRepository,
    runs: SqliteRunRepository,
    starter: SqliteRunStarter,
    finisher: SqliteRunFinisher,
    approval_policy: ToolApprovalPolicy | None = None,
    registry: ToolRegistry | None = None,
    granted_permissions: frozenset[str] = _BUILTIN_TOOL_PERMISSIONS,
    workspace_settings: ConversationWorkspaceSettings | None = None,
    file_changes: SqliteFileChangeRepository | None = None,
    file_change_snapshots: FileChangeSnapshotStore | None = None,
    browser_run_bindings: BrowserRunBindings | None = None,
    browser_page_client: BrowserPageBridgeClient | None = None,
    automations: SqliteAutomationRepository | None = None,
    automation_drafts: AutomationDraftContextStore | None = None,
    automation_execution_contexts: AutomationExecutionContextStore | None = None,
    automation_browser_service: AutomationBrowserService | None = None,
    max_steps: int = 20,
    knowledge_augmenter: KnowledgeContextAugmenter | None = None,
) -> PersistentAgentRuntime:
    base_registry = registry if registry is not None else _register_builtin_tools()

    if workspace_settings is not None:

        async def loop_for_conversation(
            run_id: RunId,
            conversation_id: ConversationId,
        ) -> AgentLoop:
            scoped_registry = await _registry_for_conversation(
                base_registry=base_registry,
                workspace_settings=workspace_settings,
                run_id=run_id,
                conversation_id=conversation_id,
                conversations=conversations,
                automations=automations,
                automation_drafts=automation_drafts,
                automation_execution_contexts=automation_execution_contexts,
                automation_browser_service=automation_browser_service,
                file_changes=file_changes,
                file_change_snapshots=file_change_snapshots,
            )
            browser_permissions = await _register_browser_tools(
                registry=scoped_registry,
                conversations=conversations,
                conversation_id=conversation_id,
                run_id=run_id,
                browser_run_bindings=browser_run_bindings,
                browser_page_client=browser_page_client,
            )
            return build_agent_loop(
                model=model,
                event_publisher=RepositoryEventPublisher(runs),
                tool_call_recorder=RepositoryToolCallRecorder(runs),
                approval_policy=approval_policy,
                registry=scoped_registry,
                granted_permissions=(
                    granted_permissions
                    | _filesystem_permissions(
                        file_changes=file_changes,
                        file_change_snapshots=file_change_snapshots,
                    )
                    | browser_permissions
                ),
                max_steps=max_steps,
                max_tool_calls_per_model_response=(1 if browser_permissions else None),
            )

        return PersistentAgentRuntime(
            conversations=conversations,
            run_submission=RunSubmissionService(
                conversations=conversations,
                run_starter=starter,
                now=now,
                new_run_id=new_run_id,
                new_message_id=new_message_id,
            ),
            run_finisher=finisher,
            loop_for_conversation=loop_for_conversation,
            system_prompt_for_conversation=lambda conversation_id, user_query, run_id: (
                _system_prompt_for_conversation(
                    workspace_settings=workspace_settings,
                    conversations=conversations,
                    conversation_id=conversation_id,
                    automations=automations,
                    automation_drafts=automation_drafts,
                    knowledge_augmenter=knowledge_augmenter,
                    user_query=user_query,
                    run_id=run_id,
                )
            ),
            now=now,
            new_message_id=new_message_id,
        )

    return PersistentAgentRuntime(
        conversations=conversations,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=now,
            new_run_id=new_run_id,
            new_message_id=new_message_id,
        ),
        run_finisher=finisher,
        loop=build_agent_loop(
            model=model,
            event_publisher=RepositoryEventPublisher(runs),
            tool_call_recorder=RepositoryToolCallRecorder(runs),
            approval_policy=approval_policy,
            registry=base_registry,
            granted_permissions=granted_permissions,
            max_steps=max_steps,
        ),
        now=now,
        new_message_id=new_message_id,
    )


def build_persistent_development_runtime(
    *,
    conversations: SqliteConversationRepository,
    runs: SqliteRunRepository,
    starter: SqliteRunStarter,
    finisher: SqliteRunFinisher,
    approval_policy: ToolApprovalPolicy | None = None,
    registry: ToolRegistry | None = None,
    granted_permissions: frozenset[str] = _BUILTIN_TOOL_PERMISSIONS,
    workspace_settings: ConversationWorkspaceSettings | None = None,
    file_changes: SqliteFileChangeRepository | None = None,
    file_change_snapshots: FileChangeSnapshotStore | None = None,
    browser_run_bindings: BrowserRunBindings | None = None,
    browser_page_client: BrowserPageBridgeClient | None = None,
    automations: SqliteAutomationRepository | None = None,
    automation_drafts: AutomationDraftContextStore | None = None,
    automation_execution_contexts: AutomationExecutionContextStore | None = None,
    automation_browser_service: AutomationBrowserService | None = None,
    max_steps: int = 20,
    knowledge_augmenter: KnowledgeContextAugmenter | None = None,
) -> PersistentAgentRuntime:
    base_registry = registry if registry is not None else _register_builtin_tools()

    if workspace_settings is not None:

        async def loop_for_conversation(
            run_id: RunId,
            conversation_id: ConversationId,
        ) -> AgentLoop:
            scoped_registry = await _registry_for_conversation(
                base_registry=base_registry,
                workspace_settings=workspace_settings,
                run_id=run_id,
                conversation_id=conversation_id,
                conversations=conversations,
                automations=automations,
                automation_drafts=automation_drafts,
                automation_execution_contexts=automation_execution_contexts,
                automation_browser_service=automation_browser_service,
                file_changes=file_changes,
                file_change_snapshots=file_change_snapshots,
            )
            browser_permissions = await _register_browser_tools(
                registry=scoped_registry,
                conversations=conversations,
                conversation_id=conversation_id,
                run_id=run_id,
                browser_run_bindings=browser_run_bindings,
                browser_page_client=browser_page_client,
            )
            return build_development_agent_loop(
                event_publisher=RepositoryEventPublisher(runs),
                tool_call_recorder=RepositoryToolCallRecorder(runs),
                approval_policy=approval_policy,
                registry=scoped_registry,
                granted_permissions=(
                    granted_permissions
                    | _filesystem_permissions(
                        file_changes=file_changes,
                        file_change_snapshots=file_change_snapshots,
                    )
                    | browser_permissions
                ),
                max_steps=max_steps,
                max_tool_calls_per_model_response=(1 if browser_permissions else None),
            )

        return PersistentAgentRuntime(
            conversations=conversations,
            run_submission=RunSubmissionService(
                conversations=conversations,
                run_starter=starter,
                now=now,
                new_run_id=new_run_id,
                new_message_id=new_message_id,
            ),
            run_finisher=finisher,
            loop_for_conversation=loop_for_conversation,
            system_prompt_for_conversation=lambda conversation_id, user_query, run_id: (
                _system_prompt_for_conversation(
                    workspace_settings=workspace_settings,
                    conversations=conversations,
                    conversation_id=conversation_id,
                    automations=automations,
                    automation_drafts=automation_drafts,
                    knowledge_augmenter=knowledge_augmenter,
                    user_query=user_query,
                    run_id=run_id,
                )
            ),
            now=now,
            new_message_id=new_message_id,
        )

    return PersistentAgentRuntime(
        conversations=conversations,
        run_submission=RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=now,
            new_run_id=new_run_id,
            new_message_id=new_message_id,
        ),
        run_finisher=finisher,
        loop=build_development_agent_loop(
            event_publisher=RepositoryEventPublisher(runs),
            tool_call_recorder=RepositoryToolCallRecorder(runs),
            approval_policy=approval_policy,
            registry=base_registry,
            granted_permissions=granted_permissions,
            max_steps=max_steps,
        ),
        now=now,
        new_message_id=new_message_id,
    )


async def get_or_create_persistent_conversation(
    *,
    conversations: ConversationRepository,
    conversation_id: ConversationId | None,
) -> Conversation:
    if conversation_id is not None:
        conversation = await conversations.get(conversation_id)
        if conversation is None:
            raise ValueError("requested conversation is unavailable")
        return conversation

    created_at = now()
    conversation = Conversation(
        conversation_id=new_conversation_id(),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )
    await conversations.save(conversation)
    return conversation


async def run_persistent_agent_chat(
    *,
    runtime: PersistentAgentRuntime,
    conversation_id: ConversationId,
    model_name: str,
    system_prompt: str,
    read_line: Callable[[str], str],
    write_line: Callable[[str], None],
) -> None:
    write_line(
        "asAgent persistent agent. "
        f"Conversation: {conversation_id}. Type 'exit' to quit.",
    )

    while True:
        try:
            content = read_line("You: ")
        except EOFError:
            return

        if content.strip().lower() in {"exit", "quit"}:
            return
        if not content.strip():
            continue

        try:
            result = await runtime.run(
                conversation_id=conversation_id,
                content=content,
                model_name=model_name,
                system_prompt=system_prompt,
            )
        except Exception as error:
            write_line(f"Error: {error}")
            continue

        if result.assistant_message is not None:
            write_line(f"asAgent: {result.assistant_message.content}")
        elif result.error is not None:
            write_line(f"Error: {result.error}")
        else:
            write_line(f"Run ended: {result.run.status.value}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the asAgent development CLI.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("chat", "serve"),
        default="chat",
        help="Run the development chat (default) or local API server.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Local API host. Only 127.0.0.1 is accepted.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Local API port. Defaults to 0 for a system-assigned port.",
    )
    parser.add_argument(
        "--bootstrap-stdin",
        action="store_true",
        help=(
            "Read one local API bootstrap JSON record from standard input. "
            "The record must contain the temporary API token."
        ),
    )
    parser.add_argument(
        "--profile",
        help="Use the named local Provider Profile instead of the offline provider.",
    )
    parser.add_argument(
        "--secret-env",
        help="Development-only environment variable bound to the selected Profile secret.",
    )
    parser.add_argument(
        "--app-home",
        type=Path,
        default=Path(".local-data"),
        help="Root containing config/providers.toml for a real Provider Profile.",
    )
    parser.add_argument(
        "--persistent",
        action="store_true",
        help="Persist conversations and Runs in SQLite.",
    )
    parser.add_argument(
        "--conversation-id",
        help="Reuse an existing Conversation in --persistent mode.",
    )
    return parser.parse_args(argv)


async def _delete_stale_automation_drafts(
    *,
    conversations: ConversationRepository,
    user_id: UserId,
) -> None:
    """Remove hidden drafts whose process-local planning context cannot be restored."""
    stale_drafts = await conversations.list_for_user(
        user_id,
        kind="automation_draft",
    )
    for draft in stale_drafts:
        await conversations.delete(draft.conversation_id)


async def _run_main(args: argparse.Namespace) -> None:
    if (args.profile is None) != (args.secret_env is None):
        raise ProviderConfigurationError(
            "--profile and --secret-env must be provided together",
        )

    secrets: SecretProvider

    if args.command == "serve":
        if not args.bootstrap_stdin:
            raise ValueError("serve requires --bootstrap-stdin")

        bootstrap = read_local_api_bootstrap(sys.stdin.readline)
        access_token = bootstrap.token
        paths = AppPaths.from_root(args.app_home)
        paths.workspace_dir.mkdir(parents=True, exist_ok=True)
        database_path = paths.data_dir / "asagent.sqlite3"
        upgrade_sqlite_database(
            database_path=database_path,
            alembic_config_path=_alembic_config_path(),
        )
        conversations = SqliteConversationRepository(database_path)
        conversation_file_scopes = SqliteConversationFileScopeRepository(database_path)
        connections = SqliteConnectionRepository(database_path)
        file_changes = SqliteFileChangeRepository(database_path)
        file_change_snapshots = FileChangeSnapshotStore(paths.data_dir)
        runs = SqliteRunRepository(database_path)
        automations = SqliteAutomationRepository(database_path)
        await _delete_stale_automation_drafts(
            conversations=conversations,
            user_id=UserId("local-user"),
        )
        automation_drafts = AutomationDraftContextStore()
        automation_execution_contexts = AutomationExecutionContextStore()
        starter = SqliteRunStarter(database_path)
        finisher = SqliteRunFinisher(database_path)
        credential_store = MacOSKeychainCredentialStore()
        tavily_settings = TavilySettings(
            config_dir=paths.config_dir,
            connections=connections,
            credential_store=credential_store,
            clock=now,
        )
        model_settings = ModelSettings(
            config_dir=paths.config_dir,
            connections=connections,
            credential_store=credential_store,
            clock=now,
        )
        agent_settings_store = AgentSettingsStore(paths.config_dir)
        agent_settings = agent_settings_store.get()
        storage_settings_store = StorageSettingsStore(paths.config_dir)
        storage_settings = storage_settings_store.get()
        file_change_snapshots.prune(storage_settings.snapshot_retention_days)
        workspace_settings = ConversationWorkspaceSettings(
            scopes=conversation_file_scopes,
            workspace_root=paths.workspace_dir,
        )
        tool_approvals = PendingToolApprovalPolicy()
        run_submission = RunSubmissionService(
            conversations=conversations,
            run_starter=starter,
            now=now,
            new_run_id=new_run_id,
            new_message_id=new_message_id,
        )
        system_prompt = (
            "You are asAgent's development assistant. Use the supplied tools when "
            "they help answer the user."
        )

        knowledge_repository = SqliteKnowledgeRepository(database_path)
        qdrant_dir = paths.data_dir / "qdrant"
        knowledge_vector_store = KnowledgeVectorStore(qdrant_dir)
        models_dir = _application_resource_path(
            "app-assets",
            "models",
            "paraphrase-multilingual-MiniLM-L12-v2",
        )
        if not models_dir.exists():
            models_dir = (
                paths.data_dir / "models" / "paraphrase-multilingual-MiniLM-L12-v2"
            )

        if models_dir.exists():
            knowledge_embedder = LocalMiniLMEmbedder(models_dir)
            knowledge_indexer = KnowledgeIndexer(
                repository=knowledge_repository,
                embedder=knowledge_embedder,
                vector_store=knowledge_vector_store,
                now=now,
            )
            knowledge_retriever = KnowledgeRetriever(
                repository=knowledge_repository,
                embedder=knowledge_embedder,
                vector_store=knowledge_vector_store,
                now=now,
            )
            knowledge_augmenter = KnowledgeContextAugmenter(
                repository=knowledge_repository,
                retriever=knowledge_retriever,
            )
        else:
            knowledge_embedder = None
            knowledge_indexer = None
            knowledge_retriever = None
            knowledge_augmenter = None

        http_client: httpx.AsyncClient | None = None
        browser_page_client: BrowserPageBridgeClient | None = None
        browser_run_bindings = BrowserRunBindings()
        automation_browser_service: AutomationBrowserService | None = None
        mcp_manager: McpServerManager | None = None
        dispatcher: InProcessRunDispatcher | None = None
        automation_scheduler: AutomationScheduler | None = None

        try:
            automation_browser_service = AutomationBrowserService(
                user_data_dir=paths.data_dir / "browser_profile",
                headless=os.environ.get("ASAGENT_AUTOMATION_HEADLESS", "").lower()
                == "true",
            )
            if bootstrap.browser_bridge is not None:
                browser_page_client = BrowserPageBridgeClient(
                    base_url=bootstrap.browser_bridge.base_url,
                    token=bootstrap.browser_bridge.token,
                )

            (
                registry,
                mcp_manager,
                has_mcp_servers,
            ) = await _start_configured_mcp_servers(
                config_dir=paths.config_dir,
                environment=os.environ,
            )
            granted_permissions = (
                _BUILTIN_TOOL_PERMISSIONS | frozenset({"mcp.execute"})
                if has_mcp_servers
                else _BUILTIN_TOOL_PERMISSIONS
            )

            configured_profile = model_settings.get_active_profile()
            if args.profile is None and configured_profile is None:
                runtime = build_persistent_development_runtime(
                    conversations=conversations,
                    runs=runs,
                    starter=starter,
                    finisher=finisher,
                    approval_policy=tool_approvals,
                    registry=registry,
                    granted_permissions=granted_permissions,
                    workspace_settings=workspace_settings,
                    file_changes=file_changes,
                    file_change_snapshots=file_change_snapshots,
                    browser_run_bindings=browser_run_bindings,
                    browser_page_client=browser_page_client,
                    automations=automations,
                    automation_drafts=automation_drafts,
                    automation_execution_contexts=automation_execution_contexts,
                    automation_browser_service=automation_browser_service,
                    max_steps=agent_settings.max_steps,
                    knowledge_augmenter=knowledge_augmenter,
                )
                model_name = "development-tools"
            else:
                if args.profile is None:
                    profile = configured_profile
                    assert profile is not None
                    profiles = ProviderProfiles(
                        providers={MODEL_PROFILE_NAME: profile},
                    )
                    profile_name = MODEL_PROFILE_NAME
                    secret_bindings: dict[str, ConnectionId] = {
                        MODEL_SECRET_ID: MODEL_CONNECTION_ID,
                    }
                    if (
                        profile.secret_id is not None
                        and profile.secret_id != MODEL_SECRET_ID
                    ):
                        secret_bindings[profile.secret_id] = MODEL_CONNECTION_ID
                    secrets = CredentialStoreSecretProvider(
                        credential_store=credential_store,
                        bindings=secret_bindings,
                    )
                else:
                    profiles = load_provider_profiles(paths.config_dir)
                    try:
                        profile = profiles.providers[args.profile]
                    except KeyError as error:
                        raise ProviderConfigurationError(
                            "requested provider profile is unavailable",
                        ) from error
                    if profile.secret_id is None:
                        raise ProviderConfigurationError(
                            "requested provider profile does not use a secret",
                        )
                    profile_name = args.profile
                    secrets = EnvironmentSecretProvider(
                        environment=dict(os.environ),
                        bindings={profile.secret_id: args.secret_env},
                    )
                http_client = httpx.AsyncClient()
                provider = create_model_provider(
                    profiles=profiles,
                    profile_name=profile_name,
                    secrets=secrets,
                    http_client=http_client,
                )
                runtime = build_persistent_agent_runtime(
                    model=provider,
                    conversations=conversations,
                    runs=runs,
                    starter=starter,
                    finisher=finisher,
                    approval_policy=tool_approvals,
                    registry=registry,
                    granted_permissions=granted_permissions,
                    workspace_settings=workspace_settings,
                    file_changes=file_changes,
                    file_change_snapshots=file_change_snapshots,
                    browser_run_bindings=browser_run_bindings,
                    browser_page_client=browser_page_client,
                    automations=automations,
                    automation_drafts=automation_drafts,
                    automation_execution_contexts=automation_execution_contexts,
                    automation_browser_service=automation_browser_service,
                    max_steps=agent_settings.max_steps,
                    knowledge_augmenter=knowledge_augmenter,
                )
                model_name = profile.model

            async def execute_submitted(
                submission: SubmittedRun,
                cancellation_token: RunCancellationToken,
            ) -> None:
                await runtime.execute_submitted(
                    submission=submission,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    cancellation_token=cancellation_token,
                )

            dispatcher = InProcessRunDispatcher(
                execute_submitted=execute_submitted,
            )
            automation_scheduler = AutomationScheduler(
                automations=automations,
                runs=runs,
                submission=AutomationRunSubmissionService(
                    conversations=conversations,
                    run_submission=run_submission,
                    now=now,
                    new_conversation_id=new_conversation_id,
                    execution_contexts=automation_execution_contexts,
                ),
                dispatcher=dispatcher,
                now=now,
            )
            await automation_scheduler.start()

            async def revert_file_change(
                file_change_id: FileChangeId,
                expected_path: Path,
            ) -> FileChange:
                change = await file_changes.get(file_change_id)
                if change is None:
                    raise FileChangeNotFoundError(
                        f"file change not found: {file_change_id}"
                    )
                service = ReversibleFileService(
                    WorkspaceResolver(workspace_root=Path(change.root_path)),
                    file_changes,
                    file_change_snapshots,
                    new_file_change_id,
                    now,
                )
                return await service.revert(
                    file_change_id,
                    expected_path=expected_path,
                )

            server = LocalApiServer(
                create_app(
                    access_token=access_token,
                    conversations=conversations,
                    runs=runs,
                    run_submission=run_submission,
                    dispatch_submitted_run=dispatcher.dispatch,
                    cancel_run=dispatcher.cancel,
                    tool_approvals=tool_approvals,
                    tavily_settings=tavily_settings,
                    model_settings=model_settings,
                    agent_settings=agent_settings_store,
                    storage_settings=storage_settings_store,
                    file_change_snapshots=file_change_snapshots,
                    workspace_settings=workspace_settings,
                    file_changes=file_changes,
                    revert_file_change=revert_file_change,
                    browser_run_bindings=browser_run_bindings,
                    automations=automations,
                    automation_drafts=automation_drafts,
                    run_automation_now_action=automation_scheduler.run_now,
                    knowledge_repository=knowledge_repository,
                    knowledge_indexer=knowledge_indexer,
                    knowledge_retriever=knowledge_retriever,
                ),
                host=args.host,
                port=args.port,
            )
            ready = await server.start()
            print(f"{READY_PREFIX}{ready.to_json()}", flush=True)
            await server.wait_closed()
        finally:
            knowledge_vector_store.close()
            await knowledge_repository.aclose()
            await tool_approvals.aclose()
            if automation_scheduler is not None:
                await automation_scheduler.aclose()
            if dispatcher is not None:
                await dispatcher.aclose()
            if automation_browser_service is not None:
                await automation_browser_service.close()
            if mcp_manager is not None:
                await mcp_manager.aclose()
            await finisher.aclose()
            await starter.aclose()
            if http_client is not None:
                await http_client.aclose()
            await runs.aclose()
            await automations.aclose()
            await file_changes.aclose()
            await conversations.aclose()
            await conversation_file_scopes.aclose()
            await connections.aclose()

        return

    system_prompt = (
        "You are asAgent's development assistant. Use the supplied tools when "
        "they help answer the user."
    )

    if args.conversation_id is not None and not args.persistent:
        raise ProviderConfigurationError(
            "--conversation-id requires --persistent",
        )

    if args.persistent:
        paths = AppPaths.from_root(args.app_home)
        paths.workspace_dir.mkdir(parents=True, exist_ok=True)
        database_path = paths.data_dir / "asagent.sqlite3"
        upgrade_sqlite_database(
            database_path=database_path,
            alembic_config_path=_alembic_config_path(),
        )

        conversations = SqliteConversationRepository(database_path)
        conversation_file_scopes = SqliteConversationFileScopeRepository(
            database_path,
        )
        runs = SqliteRunRepository(database_path)
        starter = SqliteRunStarter(database_path)
        finisher = SqliteRunFinisher(database_path)
        workspace_settings = ConversationWorkspaceSettings(
            scopes=conversation_file_scopes,
            workspace_root=paths.workspace_dir,
        )
        agent_settings = AgentSettingsStore(paths.config_dir).get()

        try:
            conversation = await get_or_create_persistent_conversation(
                conversations=conversations,
                conversation_id=(
                    ConversationId(args.conversation_id)
                    if args.conversation_id is not None
                    else None
                ),
            )

            if args.profile is None:
                runtime = build_persistent_development_runtime(
                    conversations=conversations,
                    runs=runs,
                    starter=starter,
                    finisher=finisher,
                    workspace_settings=workspace_settings,
                    max_steps=agent_settings.max_steps,
                )
                model_name = "development-tools"
                await run_persistent_agent_chat(
                    runtime=runtime,
                    conversation_id=conversation.conversation_id,
                    model_name=model_name,
                    system_prompt=system_prompt,
                    read_line=input,
                    write_line=print,
                )
                return

            profiles = load_provider_profiles(paths.config_dir)
            try:
                profile = profiles.providers[args.profile]
            except KeyError as error:
                raise ProviderConfigurationError(
                    "requested provider profile is unavailable",
                ) from error
            if profile.secret_id is None:
                raise ProviderConfigurationError(
                    "requested provider profile does not use a secret",
                )

            secrets = EnvironmentSecretProvider(
                environment=dict(os.environ),
                bindings={profile.secret_id: args.secret_env},
            )
            async with httpx.AsyncClient() as client:
                provider = create_model_provider(
                    profiles=profiles,
                    profile_name=args.profile,
                    secrets=secrets,
                    http_client=client,
                )
                await run_persistent_agent_chat(
                    runtime=build_persistent_agent_runtime(
                        model=provider,
                        conversations=conversations,
                        runs=runs,
                        starter=starter,
                        finisher=finisher,
                        workspace_settings=workspace_settings,
                        max_steps=agent_settings.max_steps,
                    ),
                    conversation_id=conversation.conversation_id,
                    model_name=profile.model,
                    system_prompt=system_prompt,
                    read_line=input,
                    write_line=print,
                )
        finally:
            await finisher.aclose()
            await starter.aclose()
            await runs.aclose()
            await conversations.aclose()
            await conversation_file_scopes.aclose()
        return

    publisher = ConsoleEventPublisher(print)
    conversation_id = new_conversation_id()

    if args.profile is None and args.secret_env is None:
        agent_loop = build_development_agent_loop(event_publisher=publisher)
        await run_agent_chat(
            agent_loop=agent_loop,
            conversation_id=conversation_id,
            model_name="development-tools",
            system_prompt=system_prompt,
            read_line=input,
            write_line=print,
            new_run_id=new_run_id,
        )
        return

    profiles = load_provider_profiles(AppPaths.from_root(args.app_home).config_dir)
    try:
        profile = profiles.providers[args.profile]
    except KeyError as error:
        raise ProviderConfigurationError(
            "requested provider profile is unavailable",
        ) from error
    if profile.secret_id is None:
        raise ProviderConfigurationError(
            "requested provider profile does not use a secret",
        )
    secrets = EnvironmentSecretProvider(
        environment=dict(os.environ),
        bindings={profile.secret_id: args.secret_env},
    )
    async with httpx.AsyncClient() as client:
        provider = create_model_provider(
            profiles=profiles,
            profile_name=args.profile,
            secrets=secrets,
            http_client=client,
        )
        await run_agent_chat(
            agent_loop=build_agent_loop(
                model=provider,
                event_publisher=publisher,
            ),
            conversation_id=conversation_id,
            model_name=profile.model,
            system_prompt=system_prompt,
            read_line=input,
            write_line=print,
            new_run_id=new_run_id,
        )


def main(argv: Sequence[str] | None = None) -> None:
    try:
        asyncio.run(_run_main(parse_args(argv)))
    except (ProviderConfigurationError, ValueError) as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
