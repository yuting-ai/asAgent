import json
from collections.abc import Mapping

from asagent.bootstrap.browser_page_bridge import (
    BrowserPageBridgeClient,
    BrowserPageBridgeError,
)
from asagent.core.tool_definition import ToolDefinition
from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError

_MAX_TARGET_ID_CHARS = 80
_MAX_TITLE_CHARS = 512
_MAX_TEXT_CHARS = 32 * 1024


class BrowserClickTool:
    """Clicks one inspected interactive target on the bound visible browser tab."""

    def __init__(self, *, client: BrowserPageBridgeClient, tab_id: str) -> None:
        self._client = client
        self._tab_id = tab_id

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="browser.click",
            display_name="Click page element",
            description=(
                "Clicks one interactive element on the browser tab that was "
                "active when this Browser conversation message was submitted. "
                "The tab must still be the user's currently visible browser "
                "tab. Accepts only a ref returned by browser.take_snapshot. "
                "Do not guess CSS selectors or "
                "use external search to infer page structure. Does not type, "
                "fill, select, or submit forms. The result may include a "
                "bounded page snapshot captured after the click settles. Use "
                "that snapshot before deciding whether the page still needs "
                "time to finish. Inspect interactive elements again before "
                "another click."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": _MAX_TARGET_ID_CHARS,
                    },
                },
                "required": ["ref"],
                "additionalProperties": False,
            },
            risk_level="high",
            required_permissions=frozenset({"browser.click"}),
            requires_approval=False,
            timeout_seconds=10.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        target_id = _require_target_id(arguments)

        try:
            result = await self._client.click_current_page(self._tab_id, target_id)
        except ToolOperationError:
            raise
        except BrowserPageBridgeError as error:
            raise _as_operation_error(error) from error

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


def _require_target_id(arguments: Mapping[str, object]) -> str:
    if set(arguments) != {"ref"}:
        raise ValueError("browser.click accepts only a ref argument")

    value = arguments["ref"]
    if not isinstance(value, str):
        raise ValueError("browser.click ref must be a string")

    target_id = value.strip()
    if target_id == "":
        raise ValueError("browser.click ref must not be blank")
    if len(target_id) > _MAX_TARGET_ID_CHARS:
        raise ValueError("browser.click ref is too long")

    return target_id


def _as_operation_error(error: BrowserPageBridgeError) -> ToolOperationError:
    message = str(error)
    if message in SAFE_BROWSER_OPERATION_ERRORS:
        return ToolOperationError(message)
    return ToolOperationError("target was not found")


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]
