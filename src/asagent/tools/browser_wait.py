import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError

_MIN_WAIT_SECONDS = 1
_MAX_WAIT_SECONDS = 30


class BrowserWaitTool:
    """Waits on one bound visible tab before a later page read."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.wait",
            display_name="Wait for page update",
            description=(
                "Waits for a visible browser page to update after an action "
                "that starts asynchronous work. seconds is always the "
                "maximum wait. The tab must remain the user's currently visible browser tab. "
                "Does not click, type, navigate, or submit anything."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "minimum": _MIN_WAIT_SECONDS,
                        "maximum": _MAX_WAIT_SECONDS,
                    },
                },
                "required": ["seconds"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"browser.wait"}),
            requires_approval=False,
            timeout_seconds=float(_MAX_WAIT_SECONDS + 5),
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        seconds = _require_seconds(arguments)
        try:
            result = await self._client.wait_for_current_page(self._tab_id, seconds)
        except ToolOperationError:
            raise
        except BrowserPageBridgeError as error:
            message = str(error)
            if message in SAFE_BROWSER_OPERATION_ERRORS:
                raise ToolOperationError(message) from error
            raise ToolOperationError("current browser tab is not visible") from error

        return json.dumps(
            {
                "changed": result.changed,
                "page": {
                    "title": result.page.title,
                    "url": result.page.url,
                    "text": result.page.text,
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def _require_seconds(arguments: Mapping[str, object]) -> int:
    if set(arguments) != {"seconds"}:
        raise ValueError("browser.wait accepts only a seconds argument")

    value = arguments["seconds"]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("browser.wait seconds must be an integer")
    if not _MIN_WAIT_SECONDS <= value <= _MAX_WAIT_SECONDS:
        raise ValueError("browser.wait seconds must be between 1 and 30")
    return value
