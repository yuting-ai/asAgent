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
_MAX_SELECT_OPTIONS = 50
_MAX_OPTION_TEXT_CHARS = 120


class BrowserInspectInteractiveTool:
    """Lists visible interactive elements on the bound browser tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.take_snapshot",
            display_name="Take page snapshot",
            description=(
                "Takes a bounded semantic snapshot of visible interactive "
                "elements on the browser tab that "
                "was active when this Browser conversation message was "
                "submitted. Returns a bounded list of ref, name, role, "
                "tag, and disabled. Native select elements also include a "
                "bounded options list with value, label, and disabled. Before "
                "clicking, filling, or selecting an unfamiliar page element, "
                "use this tool and pass its returned ref to browser.click, "
                "browser.fill, or browser.select. When the user asks you to "
                "operate the visible page, take a snapshot before claiming a "
                "browser capability is unavailable. Do not guess CSS selectors "
                "or option values, and do not use external search to infer "
                "page structure. Accepts no arguments."
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
            raise ValueError("browser.take_snapshot accepts no arguments")

        try:
            snapshot = await self._client.inspect_interactive(self._tab_id)
        except ToolOperationError:
            raise
        except BrowserPageBridgeError as error:
            raise _as_operation_error(error) from error

        elements = []
        for item in snapshot.elements[:_MAX_ELEMENTS]:
            element: dict[str, object] = {
                "ref": item.target_id,
                "name": _bounded(item.name, _MAX_NAME_CHARS),
                "role": _bounded(item.role, _MAX_ROLE_CHARS),
                "tag": _bounded(item.tag, _MAX_TAG_CHARS),
                "disabled": item.disabled,
            }
            if item.options is not None:
                element["options"] = [
                    {
                        "value": _bounded(option.value, _MAX_OPTION_TEXT_CHARS),
                        "label": _bounded(option.label, _MAX_OPTION_TEXT_CHARS),
                        "disabled": option.disabled,
                    }
                    for option in item.options[:_MAX_SELECT_OPTIONS]
                ]
            elements.append(element)

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
