from collections.abc import Mapping

from asagent.automation.browser.browser_service import AutomationBrowserService
from asagent.core.tool_definition import ToolDefinition


class AutomationBrowserNavigateTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.navigate",
            display_name="Automation browser: Navigate",
            description=(
                "Navigate the system browser to a specified web URL. Use this to open "
                "the target website for reading or automation."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The destination URL (e.g. https://news.ycombinator.com).",
                    }
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=35.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        raw_url = arguments.get("url")
        if not isinstance(raw_url, str) or not raw_url.strip():
            raise ValueError("url must be a non-empty string")
        return await self._service.navigate(raw_url.strip())


class AutomationBrowserSnapshotTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.snapshot",
            display_name="Automation browser: Snapshot",
            description=(
                "Capture a compact semantic DOM tree of the current page with numbered [ref] "
                "identifiers on all clickable, input, link, and interactive elements. Always "
                "take a snapshot before attempting to click or fill elements on an unfamiliar page."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        return await self._service.snapshot()


class AutomationBrowserClickTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.click",
            display_name="Automation browser: Click",
            description="Click an interactive element identified by its [ref] number from a snapshot.",
            input_schema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "integer",
                        "description": "The integer ref of the element to click (e.g. 3).",
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector fallback if ref is unknown.",
                    },
                },
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        ref_val = arguments.get("ref")
        selector_val = arguments.get("selector")
        ref = int(ref_val) if isinstance(ref_val, int) else None
        selector = str(selector_val).strip() if isinstance(selector_val, str) else None
        if ref is None and not selector:
            raise ValueError("Either ref or selector must be provided.")
        return await self._service.click(ref=ref, selector=selector)


class AutomationBrowserFillTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.fill",
            display_name="Automation browser: Fill text",
            description="Type or fill text into an input or textarea element by [ref] number.",
            input_schema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "integer",
                        "description": "The integer ref of the input/textarea element.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The text content to input.",
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector fallback.",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        text = arguments.get("text")
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        ref_val = arguments.get("ref")
        selector_val = arguments.get("selector")
        ref = int(ref_val) if isinstance(ref_val, int) else None
        selector = str(selector_val).strip() if isinstance(selector_val, str) else None
        if ref is None and not selector:
            raise ValueError("Either ref or selector must be provided.")
        return await self._service.fill(text=text, ref=ref, selector=selector)


class AutomationBrowserSelectTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.select",
            display_name="Automation browser: Select option",
            description="Select an option in a dropdown <select> element by value and [ref].",
            input_schema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "integer",
                        "description": "The integer ref of the select element.",
                    },
                    "value": {
                        "type": "string",
                        "description": "The option value to select.",
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector fallback.",
                    },
                },
                "required": ["value"],
                "additionalProperties": False,
            },
            risk_level="medium",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        value = arguments.get("value")
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        ref_val = arguments.get("ref")
        selector_val = arguments.get("selector")
        ref = int(ref_val) if isinstance(ref_val, int) else None
        selector = str(selector_val).strip() if isinstance(selector_val, str) else None
        if ref is None and not selector:
            raise ValueError("Either ref or selector must be provided.")
        return await self._service.select(value=value, ref=ref, selector=selector)


class AutomationBrowserWaitTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.wait",
            display_name="Automation browser: Wait",
            description="Wait for a given number of seconds for page transitions, JS rendering, or network requests.",
            input_schema={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Duration to wait in seconds (0.5 to 30.0, default 2.0).",
                    }
                },
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=35.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        seconds_val = arguments.get("seconds", 2.0)
        seconds = float(seconds_val) if isinstance(seconds_val, (int, float)) else 2.0
        return await self._service.wait(seconds=seconds)


class AutomationBrowserReadPageTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.read_page",
            display_name="Automation browser: Read page",
            description="Read the clean, full visible text content and title of the current page.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        return await self._service.read_page()


class AutomationBrowserCloseTool:
    def __init__(self, service: AutomationBrowserService) -> None:
        self._service = service

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            tool_id="automation_browser.close",
            display_name="Automation browser: Close browser",
            description=(
                "Close the automation browser instance and its window. Use this tool when "
                "you are done with web browsing tasks, or when instructed to close the browser."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            risk_level="low",
            required_permissions=frozenset({"tool.execute"}),
            requires_approval=False,
            timeout_seconds=15.0,
        )

    async def execute(self, arguments: Mapping[str, object]) -> str:
        await self._service.close()
        return "Browser closed successfully."
