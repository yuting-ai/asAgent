import json
from datetime import UTC, datetime

import httpx
import pytest
from jsonschema import Draft202012Validator

from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.cli import _register_browser_tools
from asagent.core.conversation import Conversation
from asagent.core.ids import ConversationId, RunId, UserId
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.tools.browser_click import BrowserClickTool
from asagent.tools.browser_run_bindings import BrowserRunBindings
from asagent.tools.errors import ToolArgumentsValidationError, ToolOperationError
from asagent.tools.executor import ToolExecutor
from asagent.tools.registry import ToolRegistry


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
async def test_browser_click_tool_schema_rejects_invalid_target_ids() -> None:
    tool = BrowserClickTool(
        client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:1",
            token="bridge-token",
        ),
        tab_id="tab-1",
    )
    registry = ToolRegistry()
    registry.register(tool)
    executor = ToolExecutor(
        registry,
        granted_permissions=frozenset({"browser.click"}),
    )

    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute("browser.click", {})
    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute("browser.click", {"target_id": ""})
    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute(
            "browser.click",
            {"target_id": "x" * 81},
        )
    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute(
            "browser.click",
            {"target_id": "target_1", "extra": True},
        )
    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute(
            "browser.click",
            {"selector": "button"},
        )

    Draft202012Validator(tool.definition.input_schema).validate(
        {"target_id": "target_2"},
    )
    assert tool.definition.requires_approval is False
    assert tool.definition.required_permissions == frozenset({"browser.click"})
    assert tool.definition.risk_level == "high"
    assert "inspect_interactive" in tool.definition.description


@pytest.mark.asyncio
async def test_browser_click_executor_runs_without_approval_policy() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "action": "clicked",
            "url": "https://example.com/next",
            "title": "Next page",
            "page": {
                "title": "Next page",
                "url": "https://example.com/next",
                "text": "Results are ready",
            },
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserClickTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        registry = ToolRegistry()
        registry.register(tool)
        executor = ToolExecutor(
            registry,
            granted_permissions=frozenset({"browser.click"}),
        )
        result = await executor.execute(
            "browser.click",
            {"target_id": "target_2"},
        )

    assert json.loads(result) == {
        "action": "clicked",
        "url": "https://example.com/next",
        "title": "Next page",
        "page": {
            "title": "Next page",
            "url": "https://example.com/next",
            "text": "Results are ready",
        },
    }
    assert transport.requests[0].url.path == "/click-current-page"
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-1",
        "target_id": "target_2",
    }


@pytest.mark.asyncio
async def test_browser_click_tool_posts_target_id_to_bridge() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "action": "clicked",
            "url": "https://example.com/next",
            "title": "Next page",
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserClickTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-visible",
        )
        result = await tool.execute({"target_id": "target_2"})

    assert json.loads(result) == {
        "action": "clicked",
        "url": "https://example.com/next",
        "title": "Next page",
    }
    assert transport.requests[0].url.path == "/click-current-page"
    assert transport.requests[0].headers["Authorization"] == "Bearer bridge-token"
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-visible",
        "target_id": "target_2",
    }


@pytest.mark.asyncio
async def test_browser_click_tool_maps_safe_bridge_failure() -> None:
    transport = _FakeTransport(
        status_code=409,
        payload={"detail": "target is obscured"},
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserClickTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        with pytest.raises(ToolOperationError, match="target is obscured"):
            await tool.execute({"target_id": "target_1"})


@pytest.mark.asyncio
async def test_browser_click_registers_only_for_bound_browser_runs() -> None:
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
    chat_permissions = await _register_browser_tools(
        registry=chat_registry,
        conversations=conversations,
        conversation_id=chat.conversation_id,
        run_id=RunId("run-chat"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert chat_permissions == frozenset()
    with pytest.raises(KeyError):
        chat_registry.get("browser.click")

    browser_registry = ToolRegistry()
    bindings.bind(RunId("run-browser"), "tab-2")
    browser_permissions = await _register_browser_tools(
        registry=browser_registry,
        conversations=conversations,
        conversation_id=browser.conversation_id,
        run_id=RunId("run-browser"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert browser_permissions == frozenset(
        {
            "browser.read",
            "browser.inspect",
            "browser.click",
            "browser.fill",
            "browser.wait",
        }
    )
    assert browser_registry.get("browser.click").definition.tool_id == "browser.click"
    assert (
        browser_registry.get("browser.inspect_interactive").definition.tool_id
        == "browser.inspect_interactive"
    )
    assert (
        browser_registry.get("browser.read_current_page").definition.tool_id
        == "browser.read_current_page"
    )
    assert browser_registry.get("browser.wait").definition.tool_id == "browser.wait"
    assert browser_registry.get("browser.fill").definition.tool_id == "browser.fill"

    unbound_registry = ToolRegistry()
    unbound_permissions = await _register_browser_tools(
        registry=unbound_registry,
        conversations=conversations,
        conversation_id=browser.conversation_id,
        run_id=RunId("run-unbound"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert unbound_permissions == frozenset()
    with pytest.raises(KeyError):
        unbound_registry.get("browser.click")
