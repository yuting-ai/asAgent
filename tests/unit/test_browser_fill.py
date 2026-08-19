import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.tools.browser_fill import BrowserFillTool
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
async def test_browser_fill_validates_arguments_and_posts_only_target_and_value() -> (
    None
):
    transport = _FakeTransport(
        status_code=200,
        payload={
            "action": "filled",
            "url": "https://example.com/form",
            "title": "Example form",
            "page": {
                "title": "Example form",
                "url": "https://example.com/form?draft=123",
                "text": "Draft saved",
            },
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserFillTool(
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
            registry, granted_permissions=frozenset({"browser.fill"})
        )

        with pytest.raises(ToolArgumentsValidationError):
            await executor.execute("browser.fill", {"ref": "target_1"})
        with pytest.raises(ToolArgumentsValidationError):
            await executor.execute("browser.fill", {"ref": "target_1", "value": 1})
        result = await executor.execute(
            "browser.fill", {"ref": "target_1", "value": "person@example.com"}
        )

    assert json.loads(result) == {
        "action": "filled",
        "url": "https://example.com/form",
        "title": "Example form",
        "page": {
            "title": "Example form",
            "url": "https://example.com/form?draft=123",
            "text": "Draft saved",
        },
    }
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-1",
        "target_id": "target_1",
        "value": "person@example.com",
    }
    Draft202012Validator(tool.definition.input_schema).validate(
        {"ref": "target_1", "value": ""}
    )
    assert tool.definition.required_permissions == frozenset({"browser.fill"})
    assert tool.definition.requires_approval is False


@pytest.mark.asyncio
async def test_browser_fill_returns_safe_not_editable_failure() -> None:
    transport = _FakeTransport(
        status_code=409, payload={"detail": "target is not editable"}
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserFillTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        with pytest.raises(ToolOperationError, match="target is not editable"):
            await tool.execute({"ref": "target_1", "value": "secret"})
