import json

import httpx
import pytest

from asagent.bootstrap.browser_page_bridge import BrowserPageBridgeClient
from asagent.tools.browser_input import BrowserInputTool


@pytest.mark.asyncio
async def test_native_input_binds_tab_and_reports_dispatch_only():
    requests = []

    async def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "action": "input_sent",
                "url": "https://example.com",
                "title": "Editor",
                "verified": False,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        tool = BrowserInputTool(
            client=BrowserPageBridgeClient(
                base_url="http://127.0.0.1:43124",
                token="test-token",
                http_client=http,
            ),
            tab_id="bound-tab",
        )
        result = json.loads(
            await tool.execute(
                {
                    "url": "https://example.com",
                    "kind": "text",
                    "value": "你好",
                }
            )
        )
        assert result["verified"] is False
        assert requests == [
            {
                "tab_id": "bound-tab",
                "input": {
                    "url": "https://example.com",
                    "kind": "text",
                    "value": "你好",
                },
            }
        ]
        for arguments in [
            {"url": "https://example.com", "kind": "key", "value": "Meta+L"},
            {"url": "https://example.com", "kind": "text", "value": ""},
            {
                "url": "https://example.com",
                "kind": "text",
                "value": "x",
                "tab_id": "other",
            },
        ]:
            with pytest.raises(ValueError):
                await tool.execute(arguments)
        assert len(requests) == 1
        assert tool.definition.required_permissions == frozenset({"browser.fill"})
