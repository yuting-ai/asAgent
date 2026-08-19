import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError

_MAX_TARGET_ID_CHARS = 80
_MAX_VALUE_CHARS = 512


class BrowserSelectTool:
    """Selects one inspected native select option on the bound visible browser tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.select",
            display_name="Select page option",
            description=(
                "Chooses one option on an inspected native HTML select control "
                "on the visible browser tab. Accepts only a ref returned by "
                "browser.take_snapshot and an option value from that "
                "element's options list. It does not submit the form. Custom "
                "searchable dropdowns and comboboxes are not supported; use "
                "browser.click and browser.fill for those controls."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": _MAX_TARGET_ID_CHARS,
                    },
                    "value": {"type": "string", "maxLength": _MAX_VALUE_CHARS},
                },
                "required": ["ref", "value"],
                "additionalProperties": False,
            },
            risk_level="high",
            required_permissions=frozenset({"browser.select"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        target_id, value = _require_arguments(arguments)
        try:
            result = await self._client.select_current_page(
                self._tab_id, target_id, value
            )
        except ToolOperationError:
            raise
        except BrowserPageBridgeError as error:
            message = str(error)
            if message in SAFE_BROWSER_OPERATION_ERRORS:
                raise ToolOperationError(message) from error
            raise ToolOperationError("target was not found") from error
        payload: dict[str, object] = {
            "action": result.action,
            "url": result.url,
            "title": result.title,
        }
        if result.page is not None:
            payload["page"] = {
                "title": result.page.title,
                "url": result.page.url,
                "text": result.page.text,
            }
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def _require_arguments(arguments: Mapping[str, object]) -> tuple[str, str]:
    if set(arguments) != {"ref", "value"}:
        raise ValueError("browser.select accepts only ref and value arguments")
    target_id = arguments["ref"]
    value = arguments["value"]
    if not isinstance(target_id, str) or target_id.strip() == "":
        raise ValueError("browser.select ref must not be blank")
    if len(target_id.strip()) > _MAX_TARGET_ID_CHARS:
        raise ValueError("browser.select ref is too long")
    if not isinstance(value, str):
        raise ValueError("browser.select value must be a string")
    if len(value) > _MAX_VALUE_CHARS:
        raise ValueError("browser.select value is too long")
    return target_id.strip(), value
