from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from asagent.automation.browser.browser_service import (
    AutomationBrowserService,
    _flatten_tree,
)
from asagent.automation.browser.system_browser import detect_system_browser
from asagent.automation.browser.tools import (
    AutomationBrowserClickTool,
    AutomationBrowserCloseTool,
    AutomationBrowserFillTool,
    AutomationBrowserNavigateTool,
    AutomationBrowserReadPageTool,
    AutomationBrowserSelectTool,
    AutomationBrowserSnapshotTool,
    AutomationBrowserWaitTool,
)


def test_detect_system_browser_returns_info_or_none() -> None:
    info = detect_system_browser()
    if info is not None:
        assert info.name
        assert isinstance(info.executable, Path)
        assert info.channel in {"chrome", "msedge", "chrome-beta", "chromium"}


def test_flatten_tree_formats_semantic_elements_with_refs() -> None:
    sample_tree = {
        "tag": "div",
        "children": [
            {
                "tag": "h1",
                "text": "Welcome to Hacker News",
            },
            {
                "tag": "a",
                "ref": 1,
                "href": "https://news.ycombinator.com/item?id=1",
                "text": "Top Story Link",
            },
            {
                "tag": "input",
                "ref": 2,
                "placeholder": "Search...",
                "type": "text",
            },
            {
                "tag": "button",
                "ref": 3,
                "text": "Submit",
            },
        ],
    }

    lines = _flatten_tree(sample_tree)
    assert any("h1: Welcome to Hacker News" in line for line in lines)
    assert any(
        '[1] a href="https://news.ycombinator.com/item?id=1": Top Story Link' in line
        for line in lines
    )
    assert any(
        '[2] input type="text" placeholder="Search..."' in line for line in lines
    )
    assert any("[3] button: Submit" in line for line in lines)


@pytest.mark.asyncio
async def test_automation_browser_tools_execution() -> None:
    mock_service = AsyncMock(spec=AutomationBrowserService)
    mock_service.navigate.return_value = (
        '{"url":"https://example.com","title":"Example","status":200}'
    )
    mock_service.snapshot.return_value = (
        "Page: Example (https://example.com)\n[1] button: Click Me"
    )
    mock_service.click.return_value = "Clicked element [1]."
    mock_service.fill.return_value = "Filled text into element [2]."
    mock_service.select.return_value = "Selected option 'val' on element [3]."
    mock_service.wait.return_value = "Waited 1.5s."
    mock_service.read_page.return_value = "Page text content"

    nav_tool = AutomationBrowserNavigateTool(mock_service)
    assert nav_tool.definition.tool_id == "automation_browser.navigate"
    res = await nav_tool.execute({"url": "https://example.com"})
    assert "Example" in res

    with pytest.raises(ValueError, match="non-empty string"):
        await nav_tool.execute({"url": "   "})

    snap_tool = AutomationBrowserSnapshotTool(mock_service)
    assert snap_tool.definition.tool_id == "automation_browser.snapshot"
    assert "Page:" in await snap_tool.execute({})

    click_tool = AutomationBrowserClickTool(mock_service)
    assert click_tool.definition.tool_id == "automation_browser.click"
    assert "Clicked" in await click_tool.execute({"ref": 1})

    with pytest.raises(ValueError, match="Either ref or selector"):
        await click_tool.execute({})

    fill_tool = AutomationBrowserFillTool(mock_service)
    assert fill_tool.definition.tool_id == "automation_browser.fill"
    assert "Filled" in await fill_tool.execute({"ref": 2, "text": "hello"})

    select_tool = AutomationBrowserSelectTool(mock_service)
    assert select_tool.definition.tool_id == "automation_browser.select"
    assert "Selected" in await select_tool.execute({"ref": 3, "value": "val"})

    wait_tool = AutomationBrowserWaitTool(mock_service)
    assert wait_tool.definition.tool_id == "automation_browser.wait"
    assert "Waited" in await wait_tool.execute({"seconds": 1.5})

    read_tool = AutomationBrowserReadPageTool(mock_service)
    assert read_tool.definition.tool_id == "automation_browser.read_page"
    assert "Page text content" in await read_tool.execute({})

    close_tool = AutomationBrowserCloseTool(mock_service)
    assert close_tool.definition.tool_id == "automation_browser.close"
    assert "Browser closed successfully" in await close_tool.execute({})
    mock_service.close.assert_awaited_once()


def test_chrome_cdp_launcher_initialization(tmp_path: Path) -> None:
    from asagent.automation.browser.cdp_launcher import ChromeCdpLauncher

    launcher = ChromeCdpLauncher(
        executable=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        user_data_dir=tmp_path / "profile",
        headless=False,
    )
    assert launcher.port is None
    assert launcher.endpoint == ""
    assert not launcher.is_alive()
