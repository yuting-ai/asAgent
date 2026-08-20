import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import ToolOperationError

_MAX_TITLE_CHARS = 512
_MAX_TEXT_CHARS = 32 * 1024


class BrowserNavigateTool:
    """Navigates the bound visible browser tab to a specified URL or search term."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.navigate",
            display_name="Navigate to URL",
            description=(
                "Navigates the active browser tab to a specified web URL or search "
                "keywords. Returns JSON with the navigated URL, page title, and "
                "the visible text of the loaded page. The tab must still be the "
                "user's currently visible browser tab. Does not allow non-web schemes "
                "(file:, javascript:, data:, etc.)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to (e.g. https://github.com or search keywords).",
                    }
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"browser.navigate"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        raw_url = arguments.get("url")
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise ValueError("url must be a non-blank string")

        try:
            result = await self._client.navigate_current_page(
                self._tab_id, raw_url.strip()
            )
        except (BrowserPageBridgeError, ToolOperationError) as error:
            raise ValueError(str(error)) from error

        payload: dict[str, object] = {
            "action": result.action,
            "url": result.url,
            "title": _bounded(result.title, _MAX_TITLE_CHARS),
        }
        if result.page is not None:
            payload["page"] = {
                "title": _bounded(result.page.title, _MAX_TITLE_CHARS),
                "url": result.page.url,
                "text": _bounded(result.page.text, _MAX_TEXT_CHARS),
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]
