import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError

_KEYS = [
    "Enter",
    "Tab",
    "Escape",
    "Backspace",
    "Delete",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "ArrowDown",
    "Home",
    "End",
    "SelectAll",
    "Undo",
    "Redo",
    "Shift+Enter",
    "Shift+Tab",
]


class BrowserInputTool:
    """Native input on the bound tab's focused editor, without replacing its DOM."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.input",
            display_name="Type in page editor",
            description=(
                "Insert text at the current editor selection, or send an editing key. "
                "First take a snapshot and click the intended editor to establish focus; "
                "pass its current page URL. Useful for rich editors such as Docs and Sheets "
                "where fill cannot update the document model. Text replaces only the selection, "
                "not the whole field. Keys: " + ", ".join(_KEYS) + ". "
                "Password fields are forbidden. Do not type credentials. "
                "Enter/Tab may commit changes or submit a form; use only for the requested action. "
                "The result confirms input dispatch only, NOT that content was saved. "
                "The observation contains before/after focus identity, bounded editor text, "
                "selection offsets, nearby name-box/formula controls and visible status messages. "
                "changed indicates observable UI changes, NOT saved content. Compare these states: "
                "a name box selects a cell range; it is not the cell editor. In Sheets, editor text "
                "may be only an uncommitted staging buffer. After entering a cell, commit once, "
                "move away and reselect that cell to check its formula value or visible contents. "
                "Do not claim success from staging text alone. Verify one cell before entering a table. "
                "In Sheets, newline/Tab in text are editing keys; prefer one cell per input. "
                "Do not use SelectAll/Delete/Backspace to repair uncertain input: selection may "
                "cover the entire sheet. If state is unchanged, "
                "do not blindly repeat Enter. Reinspect and locate the intended editor. "
                "Null observations or page/tab changes mean verification is unavailable; "
                "do not resend text automatically, because the edit may already have occurred. "
                "Inspect and verify the result before reporting success or retrying. "
                "If no editor is focused, click the editor or ask the user to place the caret; "
                "do not repeatedly call fill on a canvas."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1, "maxLength": 8192},
                    "kind": {"type": "string", "enum": ["text", "key"]},
                    "value": {"type": "string", "minLength": 1, "maxLength": 10000},
                },
                "required": ["url", "kind", "value"],
                "additionalProperties": False,
            },
            risk_level="high",
            required_permissions=frozenset({"browser.fill"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        if set(arguments) != {"url", "kind", "value"}:
            raise ValueError("browser.input accepts only url, kind and value")
        url, kind, value = (arguments[k] for k in ("url", "kind", "value"))
        if not isinstance(url, str) or not url or len(url) > 8192:
            raise ValueError("invalid page URL")
        if (
            kind not in ("text", "key")
            or not isinstance(value, str)
            or not 0 < len(value) <= 10000
        ):
            raise ValueError("invalid browser input")
        if kind == "key" and value not in _KEYS:
            raise ValueError("unsupported editing key")
        try:
            result = await self._client.input_current_page(
                self._tab_id, url=url, kind=str(kind), value=value
            )
        except BrowserPageBridgeError as error:
            message = str(error)
            raise ToolOperationError(
                message
                if message in SAFE_BROWSER_OPERATION_ERRORS
                else "target is not editable"
            ) from error
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
