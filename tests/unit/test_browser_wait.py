import json

import httpx
import pytest
from jsonschema import Draft202012Validator

from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.tools.browser_wait import BrowserWaitTool
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
async def test_browser_wait_validates_a_bounded_integer_seconds_argument() -> None:
    tool = BrowserWaitTool(
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
        granted_permissions=frozenset({"browser.wait"}),
    )

    for arguments in (
        {},
        {"seconds": 0},
        {"seconds": 31},
        {"seconds": True},
        {"seconds": 1, "until_text": "Result"},
    ):
        with pytest.raises(ToolArgumentsValidationError):
            await executor.execute("browser.wait", arguments)

    Draft202012Validator(tool.definition.input_schema).validate({"seconds": 15})
    assert tool.definition.requires_approval is False
    assert tool.definition.required_permissions == frozenset({"browser.wait"})
    assert "maximum wait" in tool.definition.description


@pytest.mark.asyncio
async def test_browser_wait_posts_to_the_visible_tab_bridge() -> None:
    transport = _FakeTransport(
        status_code=200,
        payload={
            "changed": True,
            "page": {
                "title": "Results",
                "url": "https://example.com/next",
                "text": "Results are ready",
            },
        },
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserWaitTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-visible",
        )
        result = await tool.execute({"seconds": 15})

    assert json.loads(result) == {
        "changed": True,
        "page": {
            "title": "Results",
            "url": "https://example.com/next",
            "text": "Results are ready",
        },
    }
    assert transport.requests[0].url.path == "/wait-for-current-page"
    assert json.loads(transport.requests[0].content.decode()) == {
        "tab_id": "tab-visible",
        "seconds": 15,
    }


@pytest.mark.asyncio
async def test_browser_wait_maps_visible_tab_failure() -> None:
    transport = _FakeTransport(
        status_code=409,
        payload={"detail": "current browser tab is not visible"},
    )
    async with httpx.AsyncClient(transport=transport) as client:
        tool = BrowserWaitTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="bridge-token",
                http_client=client,
            ),
            tab_id="tab-1",
        )
        with pytest.raises(
            ToolOperationError, match="current browser tab is not visible"
        ):
            await tool.execute({"seconds": 1})
