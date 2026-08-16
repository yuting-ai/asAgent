import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError

_MAX_ELEMENTS = 80
_MAX_NAME_CHARS = 120
_MAX_ROLE_CHARS = 40
_MAX_TAG_CHARS = 40
_MAX_URL_CHARS = 2048


class BrowserInspectInteractiveTool:
    """Lists visible interactive elements on the bound browser tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.inspect_interactive",
            display_name="Inspect interactive elements",
            description=(
                "Lists visible interactive elements on the browser tab that "
                "was active when this Browser conversation message was "
                "submitted. Returns a bounded list of target_id, name, role, "
                "tag, and disabled. Before clicking an unfamiliar page "
                "element, use this tool and pass a returned target_id to "
                "browser.click. Do not guess CSS selectors or use external "
                "search to infer page structure. Accepts no arguments."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"browser.inspect"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        if arguments:
            raise ValueError("browser.inspect_interactive accepts no arguments")

        try:
            snapshot = await self._client.inspect_interactive(self._tab_id)
        except ToolOperationError:
            raise
        except BrowserPageBridgeError as error:
            raise _as_operation_error(error) from error

        elements = []
        for item in snapshot.elements[:_MAX_ELEMENTS]:
            elements.append(
                {
                    "target_id": item.target_id,
                    "name": _bounded(item.name, _MAX_NAME_CHARS),
                    "role": _bounded(item.role, _MAX_ROLE_CHARS),
                    "tag": _bounded(item.tag, _MAX_TAG_CHARS),
                    "disabled": item.disabled,
                }
            )

        payload = {
            "url": _bounded(snapshot.url, _MAX_URL_CHARS),
            "elements": elements,
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _as_operation_error(error: BrowserPageBridgeError) -> ToolOperationError:
    message = str(error)
    if message in SAFE_BROWSER_OPERATION_ERRORS:
        return ToolOperationError(message)
    return ToolOperationError("current browser tab is not visible")


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]
