from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from asagent.automation.browser.browser_service import AutomationBrowserService
from asagent.chat.service import ChatService
from asagent.cli import (
    _delete_stale_automation_drafts,
    _registry_for_conversation,
    run_chat,
)
from asagent.core.conversation import Conversation, ConversationKind
from asagent.core.conversation_file_scope import ConversationFileScope
from asagent.core.ids import ConversationId, MessageId, RunId, UserId
from asagent.core.tool_definition import ToolDefinition
from asagent.models.contracts import ModelResponse
from asagent.models.fake_provider import FakeModelProvider
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.tools.builtin.echo import EchoTool
from asagent.tools.registry import ToolRegistry
from asagent.workspace.settings import ConversationWorkspaceSettings


class InMemoryConversationFileScopeRepository:
    async def get(self, conversation_id: ConversationId) -> ConversationFileScope:
        return ConversationFileScope(conversation_id=conversation_id)

    async def save(self, scope: ConversationFileScope) -> None:
        del scope


class TavilySearchTool:
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="mcp:tavily:tavily_search:test",
            display_name="tavily_search",
            description="Search the web with Tavily.",
            input_schema={"type": "object"},
            risk_level="medium",
            required_permissions=frozenset({"mcp.execute"}),
            requires_approval=True,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        del arguments
        return "not used"


def make_conversation() -> Conversation:
    created_at = datetime(2026, 8, 6, 9, 0, tzinfo=UTC)
    return Conversation(
        conversation_id=ConversationId("conv_123"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
    )


def make_chat_service(
    *,
    repository: InMemoryConversationRepository,
    provider: FakeModelProvider,
    timestamps: Iterator[datetime],
    message_ids: Iterator[MessageId],
) -> ChatService:
    def now() -> datetime:
        return next(timestamps)

    def new_message_id() -> MessageId:
        return next(message_ids)

    return ChatService(
        conversations=repository,
        model_provider=provider,
        now=now,
        new_message_id=new_message_id,
    )


@pytest.mark.asyncio
async def test_sidecar_startup_deletes_only_stale_automation_drafts() -> None:
    repository = InMemoryConversationRepository()
    created_at = datetime(2026, 8, 23, 1, 0, tzinfo=UTC)
    chat = Conversation(
        ConversationId("chat"), UserId("local-user"), created_at, created_at
    )
    draft = Conversation(
        ConversationId("draft"),
        UserId("local-user"),
        created_at,
        created_at,
        kind="automation_draft",
    )
    execution = Conversation(
        ConversationId("execution"),
        UserId("local-user"),
        created_at,
        created_at,
        kind="automation_execution",
    )
    await repository.save(chat)
    await repository.save(draft)
    await repository.save(execution)

    await _delete_stale_automation_drafts(
        conversations=repository,
        user_id=UserId("local-user"),
    )

    assert await repository.get(draft.conversation_id) is None
    assert await repository.get(chat.conversation_id) == chat
    assert await repository.get(execution.conversation_id) == execution


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expects_tavily", "expects_automation_browser"),
    (
        ("chat", True, False),
        ("browser", False, False),
        ("automation_execution", False, True),
    ),
)
async def test_conversation_kind_scopes_specialized_tool_snapshots(
    tmp_path: Path,
    kind: ConversationKind,
    expects_tavily: bool,
    expects_automation_browser: bool,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    conversations = InMemoryConversationRepository()
    conversation_id = ConversationId(f"conversation-{kind}")
    created_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    await conversations.save(
        Conversation(
            conversation_id,
            UserId("local-user"),
            created_at,
            created_at,
            kind=kind,
        )
    )
    base_registry = ToolRegistry()
    base_registry.register(EchoTool())
    base_registry.register(TavilySearchTool())

    registry = await _registry_for_conversation(
        base_registry=base_registry,
        workspace_settings=ConversationWorkspaceSettings(
            scopes=InMemoryConversationFileScopeRepository(),
            workspace_root=workspace_root,
        ),
        run_id=RunId("run-test"),
        conversation_id=conversation_id,
        conversations=conversations,
        automation_browser_service=AsyncMock(spec=AutomationBrowserService),
    )

    tool_ids = {definition.tool_id for definition in registry.definitions()}
    assert "builtin.echo" in tool_ids
    assert ("mcp:tavily:tavily_search:test" in tool_ids) is expects_tavily
    assert (
        any(tool_id.startswith("automation_browser.") for tool_id in tool_ids)
        is expects_automation_browser
    )


@pytest.mark.asyncio
async def test_cli_runs_multiple_turns_until_exit() -> None:
    repository = InMemoryConversationRepository()
    provider = FakeModelProvider(
        responses=(
            ModelResponse(text="Hello!", tool_calls=()),
            ModelResponse(text="I am asAgent.", tool_calls=()),
        ),
    )
    chat_service = make_chat_service(
        repository=repository,
        provider=provider,
        timestamps=iter(
            (
                datetime(2026, 8, 6, 9, 1, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 2, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 3, tzinfo=UTC),
                datetime(2026, 8, 6, 9, 4, tzinfo=UTC),
            ),
        ),
        message_ids=iter(
            (
                MessageId("msg_user_1"),
                MessageId("msg_assistant_1"),
                MessageId("msg_user_2"),
                MessageId("msg_assistant_2"),
            ),
        ),
    )
    inputs = iter(("Hello, asAgent.", "Who are you?", "exit"))
    output: list[str] = []

    def read_line(prompt: str) -> str:
        assert prompt == "You: "
        return next(inputs)

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=read_line,
        write_line=output.append,
    )

    assert output == [
        "asAgent development chat. Type 'exit' to quit.",
        "asAgent: Hello!",
        "asAgent: I am asAgent.",
    ]
    assert len(provider.requests) == 2


@pytest.mark.asyncio
async def test_cli_reports_provider_errors_and_returns_to_input() -> None:
    repository = InMemoryConversationRepository()
    chat_service = make_chat_service(
        repository=repository,
        provider=FakeModelProvider(),
        timestamps=iter((datetime(2026, 8, 6, 9, 1, tzinfo=UTC),)),
        message_ids=iter((MessageId("msg_user_1"),)),
    )
    output: list[str] = []
    inputs = iter(("Hello, asAgent.", "exit"))

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=lambda _: next(inputs),
        write_line=output.append,
    )

    assert output == [
        "asAgent development chat. Type 'exit' to quit.",
        "Error: no scripted response available",
    ]


@pytest.mark.asyncio
async def test_cli_stops_cleanly_on_end_of_input() -> None:
    repository = InMemoryConversationRepository()
    chat_service = make_chat_service(
        repository=repository,
        provider=FakeModelProvider(),
        timestamps=iter(()),
        message_ids=iter(()),
    )
    output: list[str] = []

    def read_line(_: str) -> str:
        raise EOFError

    await run_chat(
        chat_service=chat_service,
        conversation=make_conversation(),
        model_name="fake-model",
        system_prompt="You are a helpful assistant.",
        read_line=read_line,
        write_line=output.append,
    )

    assert output == ["asAgent development chat. Type 'exit' to quit."]
