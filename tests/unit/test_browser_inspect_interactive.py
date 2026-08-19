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
from asagent.tools.browser_inspect_interactive import BrowserInspectInteractiveTool
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
async def test_browser_inspect_interactive_rejects_arguments() -> None:
    tool = BrowserInspectInteractiveTool(
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
        granted_permissions=frozenset({"browser.inspect"}),
    )

    with pytest.raises(ToolArgumentsValidationError):
        await executor.execute(
            "browser.take_snapshot",
            {"extra": True},
        )

    Draft202012Validator(tool.definition.input_schema).validate({})
    assert tool.definition.tool_id == "browser.take_snapshot"
    assert tool.definition.required_permissions == frozenset({"browser.inspect"})
    assert "ref" in tool.definition.description


@pytest.mark.asyncio
async def test_browser_inspect_interactive_returns_bounded_elements() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "url": "https://mofs.dev/",
            "elements": [
                {
                    "target_id": "target_1",
                    "name": "Upload File",
                    "role": "clickable",
                    "tag": "div",
                    "disabled": False,
                },
                {
                    "target_id": "target_2",
                    "name": "Use Sample",
                    "role": "clickable",
                    "tag": "div",
                    "disabled": False,
                },
            ],
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserInspectInteractiveTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        result = await tool.execute({})

    assert json.loads(result) == {
        "url": "https://mofs.dev/",
        "elements": [
            {
                "ref": "target_1",
                "name": "Upload File",
                "role": "clickable",
                "tag": "div",
                "disabled": False,
            },
            {
                "ref": "target_2",
                "name": "Use Sample",
                "role": "clickable",
                "tag": "div",
                "disabled": False,
            },
        ],
    }
    assert transport.requests[0].url.path == "/inspect-interactive"
    assert json.loads(transport.requests[0].content.decode()) == {"tab_id": "tab-1"}
    assert "selector" not in result


@pytest.mark.asyncio
async def test_browser_inspect_interactive_returns_native_select_options() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "url": "https://example.com/form",
            "elements": [
                {
                    "target_id": "target_4",
                    "name": "Country",
                    "role": "combobox",
                    "tag": "select",
                    "disabled": False,
                    "options": [
                        {"value": "au", "label": "Australia", "disabled": False},
                        {"value": "us", "label": "United States", "disabled": False},
                    ],
                }
            ],
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserInspectInteractiveTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        result = await tool.execute({})

    assert json.loads(result) == {
        "url": "https://example.com/form",
        "elements": [
            {
                "ref": "target_4",
                "name": "Country",
                "role": "combobox",
                "tag": "select",
                "disabled": False,
                "options": [
                    {"value": "au", "label": "Australia", "disabled": False},
                    {"value": "us", "label": "United States", "disabled": False},
                ],
            }
        ],
    }
    assert "selector" not in result


@pytest.mark.asyncio
async def test_browser_inspect_interactive_maps_safe_bridge_failure() -> None:
    transport = _FakeTransport(
        status_code=409,
        payload={"detail": "current browser tab is not visible"},
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserInspectInteractiveTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        with pytest.raises(
            ToolOperationError,
            match="current browser tab is not visible",
        ):
            await tool.execute({})


@pytest.mark.asyncio
async def test_browser_inspect_registers_only_for_bound_browser_runs() -> None:
    created_at = datetime(2026, 8, 16, tzinfo=UTC)
    conversations = InMemoryConversationRepository()
    browser = Conversation(
        conversation_id=ConversationId("browser-1"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        kind="browser",
    )
    await conversations.save(browser)
    bindings = BrowserRunBindings()
    client = BrowserPageBridgeClient(
        base_url="http://127.0.0.1:43124",
        token="bridge-token",
    )

    registry = ToolRegistry()
    bindings.bind(RunId("run-browser"), "tab-2")
    permissions = await _register_browser_tools(
        registry=registry,
        conversations=conversations,
        conversation_id=browser.conversation_id,
        run_id=RunId("run-browser"),
        browser_run_bindings=bindings,
        browser_page_client=client,
    )
    assert "browser.inspect" in permissions
    assert (
        registry.get("browser.take_snapshot").definition.tool_id
        == "browser.take_snapshot"
    )
