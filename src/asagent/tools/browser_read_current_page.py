import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition

_MAX_TITLE_CHARS = 512
_MAX_TEXT_CHARS = 32 * 1024


class BrowserReadCurrentPageTool:
    """Reads the title, scrubbed URL, and bounded text of one bound visible tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.read_current_page",
            display_name="Read current page",
            description=(
                "Reads the title, URL, and visible text of the browser tab "
                "that was active when this Browser conversation message was "
                "submitted. The tab must still be the user's currently visible "
                "browser tab. Returns JSON with title, url, and text fields. "
                "Does not click, type, navigate, or read cookies. "
                "If reading fails or times out, do not call this tool again "
                "in the same run; tell the user the current tab could not be read."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"browser.read"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        if arguments:
            raise ValueError("browser.read_current_page accepts no arguments")

        try:
            page = await self._client.read_current_page(self._tab_id)
        except BrowserPageBridgeError as error:
            raise ValueError(str(error)) from error

        payload = {
            "title": _bounded(page.title, _MAX_TITLE_CHARS),
            "url": page.url,
            "text": _bounded(page.text, _MAX_TEXT_CHARS),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]
