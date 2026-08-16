import json
from datetime import UTC, datetime

import httpx
import pytest

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageContent,
)
from asagent.cli import _register_browser_read_tool, build_development_agent_loop
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, RunId, UserId
from asagent.core.run_event import RunEvent
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.tools.browser_read_current_page import BrowserReadCurrentPageTool
from asagent.tools.browser_run_bindings import BrowserRunBindings
from asagent.tools.registry import ToolRegistry


class _NoopEventPublisher:
    async def publish(self, event: RunEvent) -> None:
        del event


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self.payload = payload
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(
            self.status_code,
            json=self.payload,
            request=request,
        )


@pytest.mark.asyncio
async def test_browser_read_current_page_tool_rejects_arguments() -> None:
    tool = BrowserReadCurrentPageTool(
        client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:1",
            token="bridge-token",
        ),
        tab_id="tab-1",
    )

    with pytest.raises(ValueError, match="no arguments"):
        await tool.execute({"path": "/"})


@pytest.mark.asyncio
async def test_browser_read_current_page_tool_returns_bounded_json() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "title": "Example Domain",
            "url": "https://example.com/",
            "text": "Example Domain",
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserReadCurrentPageTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        result = await tool.execute({})

    assert tool.definition.tool_id == "browser.read_current_page"
    assert tool.definition.required_permissions == frozenset({"browser.read"})
    assert "do not call this tool again" in tool.definition.description
    assert tool.definition.input_schema == {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }
    assert json.loads(result) == {
        "title": "Example Domain",
        "url": "https://example.com/",
        "text": "Example Domain",
    }
    assert transport.requests[0].headers["Authorization"] == "Bearer bridge-token"
    assert json.loads(transport.requests[0].content.decode()) == {"tab_id": "tab-1"}


def test_browser_run_bindings_are_one_shot() -> None:
    bindings = BrowserRunBindings()
    run_id = RunId("run-1")
    bindings.bind(run_id, "tab-1")

    assert bindings.take(run_id) == "tab-1"
    assert bindings.take(run_id) is None


def test_browser_page_content_dataclass() -> None:
    page = BrowserPageContent(title="T", url="https://example.com/", text="Body")
    assert page.title == "T"


@pytest.mark.asyncio
async def test_browser_read_tool_registers_only_for_bound_browser_runs() -> None:
    created_at = datetime(2026, 8, 16, tzinfo=UTC)
    conversations = InMemoryConversationRepository()
    chat = Conversation(
        conversation_id=ConversationId("chat-1"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        kind="chat",
    )
    browser = Conversation(
        conversation_id=ConversationId("browser-1"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        kind="browser",
    )
    await conversations.save(chat)
    await conversations.save(browser)

    bindings = BrowserRunBindings()
    client = BrowserPageBridgeClient(
        base_url="http://127.0.0.1:43124",
        token="bridge-token",
    )

    chat_registry = ToolRegistry()
    bindings.bind(RunId("run-chat"), "tab-1")
    chat_permissions = await _register_browser_read_tool(
        registry=chat_registry,
        conversations=conversations,
        conversation_id=chat.conversation_id,
        run_id=RunId("run-chat"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert chat_permissions == frozenset()
    with pytest.raises(KeyError):
        chat_registry.get("browser.read_current_page")

    browser_registry = ToolRegistry()
    bindings.bind(RunId("run-browser"), "tab-2")
    browser_permissions = await _register_browser_read_tool(
        registry=browser_registry,
        conversations=conversations,
        conversation_id=browser.conversation_id,
        run_id=RunId("run-browser"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert browser_permissions == frozenset({"browser.read"})
    assert (
        browser_registry.get("browser.read_current_page").definition.tool_id
        == "browser.read_current_page"
    )

    unbound_registry = ToolRegistry()
    unbound_permissions = await _register_browser_read_tool(
        registry=unbound_registry,
        conversations=conversations,
        conversation_id=browser.conversation_id,
        run_id=RunId("run-unbound"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert unbound_permissions == frozenset()
    with pytest.raises(KeyError):
        unbound_registry.get("browser.read_current_page")


def test_build_development_agent_loop_forwards_max_calls_per_tool_input() -> None:
    limited = build_development_agent_loop(
        event_publisher=_NoopEventPublisher(),
        max_calls_per_tool_input=1,
    )
    unlimited = build_development_agent_loop(
        event_publisher=_NoopEventPublisher(),
    )

    assert limited._max_calls_per_tool_input == 1
    assert unlimited._max_calls_per_tool_input is None
