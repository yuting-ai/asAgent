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
from asagent.tools.browser_run_bindings import BrowserRunBindings
from asagent.tools.browser_select import BrowserSelectTool
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
        return httpx.Response(self.status_code, json=self.payload, request=request)


@pytest.mark.asyncio
async def test_browser_select_validates_arguments_and_posts_only_target_and_value() -> (
    None
):
    transport = _FakeTransport(
        status_code=200,
        payload={
            "action": "selected",
            "url": "https://example.com/form",
            "title": "Country form",
            "page": {
                "title": "Country form",
                "url": "https://example.com/form",
                "text": "Australia selected",
            },
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserSelectTool(
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
            registry, granted_permissions=frozenset({"browser.select"})
        )

        with pytest.raises(ToolArgumentsValidationError):
            await executor.execute("browser.select", {"ref": "target_4"})
        with pytest.raises(ToolArgumentsValidationError):
            await executor.execute("browser.select", {"ref": "target_4", "value": 1})
        result = await executor.execute(
            "browser.select", {"ref": "target_4", "value": "au"}
        )

    assert json.loads(result) == {
        "action": "selected",
        "url": "https://example.com/form",
        "title": "Country form",
        "page": {
            "title": "Country form",
            "url": "https://example.com/form",
            "text": "Australia selected",
        },
    }
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-1",
        "target_id": "target_4",
        "value": "au",
    }
    Draft202012Validator(tool.definition.input_schema).validate(
        {"ref": "target_4", "value": ""}
    )
    assert tool.definition.required_permissions == frozenset({"browser.select"})
    assert tool.definition.requires_approval is False
    assert tool.definition.risk_level == "high"
    assert "native" in tool.definition.description.lower()
    assert "does not submit" in tool.definition.description.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "detail",
    [
        "target is not selectable",
        "option was not found",
        "option is disabled",
    ],
)
async def test_browser_select_maps_fixed_operation_errors(detail: str) -> None:
    transport = _FakeTransport(status_code=409, payload={"detail": detail})
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserSelectTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        with pytest.raises(ToolOperationError, match=detail):
            await tool.execute({"ref": "target_4", "value": "au"})


@pytest.mark.asyncio
async def test_browser_select_registers_only_for_bound_browser_runs() -> None:
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
        chat_registry.get("browser.select")

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
    assert "browser.select" in browser_permissions
    assert browser_registry.get("browser.select").definition.tool_id == "browser.select"

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
        unbound_registry.get("browser.select")
