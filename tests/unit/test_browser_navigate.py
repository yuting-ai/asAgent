import json
from datetime import UTC, datetime

import httpx
import pytest

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
)
from asagent.cli import _register_browser_tools
from asagent.core.conversation import Conversation, ConversationKind
from asagent.core.ids import ConversationId, RunId, UserId
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from asagent.tools.browser_navigate import BrowserNavigateTool
from asagent.tools.browser_run_bindings import BrowserRunBindings
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
async def test_browser_navigate_tool_rejects_missing_or_blank_url() -> None:
    tool = BrowserNavigateTool(
        client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:1",
            token="bridge-token",
        ),
        tab_id="tab-1",
    )

    with pytest.raises(ValueError, match="url must be a non-blank string"):
        await tool.execute({})

    with pytest.raises(ValueError, match="url must be a non-blank string"):
        await tool.execute({"url": "   "})


@pytest.mark.asyncio
async def test_browser_navigate_tool_returns_navigated_payload() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "action": "navigated",
            "url": "https://github.com/",
            "title": "GitHub",
            "page": {
                "title": "GitHub",
                "url": "https://github.com/",
                "text": "Where the world builds software",
            },
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserNavigateTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        result = await tool.execute({"url": "github.com"})

    assert tool.definition.tool_id == "browser.navigate"
    assert tool.definition.required_permissions == frozenset({"browser.navigate"})
    assert tool.definition.risk_level == "low"
    assert tool.definition.requires_approval is False
    assert json.loads(result) == {
        "action": "navigated",
        "url": "https://github.com/",
        "title": "GitHub",
        "page": {
            "title": "GitHub",
            "url": "https://github.com/",
            "text": "Where the world builds software",
        },
    }
    assert transport.requests[0].headers["Authorization"] == "Bearer bridge-token"
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-1",
        "url": "github.com",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["browser", "automation_draft"])
async def test_register_browser_tools_includes_navigate(kind: ConversationKind) -> None:
    conversations = InMemoryConversationRepository()
    created_at = datetime.now(UTC)
    conversation = Conversation(
        conversation_id=ConversationId("conv-browser"),
        user_id=UserId("local-user"),
        created_at=created_at,
        updated_at=created_at,
        kind=kind,
    )
    await conversations.save(conversation)

    bindings = BrowserRunBindings()
    bindings.bind(RunId("run-1"), "tab-1")
    registry = ToolRegistry()
    permissions = await _register_browser_tools(
        registry=registry,
        conversations=conversations,
        conversation_id=conversation.conversation_id,
        run_id=RunId("run-1"),
        browser_run_bindings=bindings,
        browser_page_client=BrowserPageBridgeClient(
            base_url="http://127.0.0.1:1",
            token="bridge-token",
        ),
    )

    assert registry.get("browser.navigate").definition.tool_id == "browser.navigate"
    assert "browser.navigate" in permissions
