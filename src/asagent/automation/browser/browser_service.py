import asyncio
import json
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from asagent.automation.browser.cdp_launcher import ChromeCdpLauncher
from asagent.automation.browser.system_browser import detect_system_browser

_INTERACTIVE_TAGS = [
    "a",
    "button",
    "input",
    "textarea",
    "select",
    "option",
    "label",
    "details",
    "summary",
]
_SEMANTIC_TAGS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "li",
    "td",
    "th",
    "caption",
    "figcaption",
    "blockquote",
    "pre",
    "code",
    "nav",
    "main",
    "article",
    "section",
    "header",
    "footer",
    "form",
    "table",
    "img",
    "video",
    "audio",
]
_KEEP_TAGS = _INTERACTIVE_TAGS + _SEMANTIC_TAGS

_SNAPSHOT_JS = f"""
() => {{
    const KEEP = new Set({json.dumps(_KEEP_TAGS)});
    const INTERACTIVE = new Set({json.dumps(_INTERACTIVE_TAGS)});
    const SKIP = new Set(["script","style","noscript","svg","path","meta","link","br","hr"]);
    const CLICKABLE_ROLES = new Set([
        "button","link","tab","menuitem","menuitemcheckbox","menuitemradio",
        "option","switch","checkbox","radio","combobox","searchbox","slider",
        "spinbutton","textbox","treeitem"
    ]);
    let refCounter = 0;
    const refMap = {{}};

    function visible(el) {{
        if (!(el instanceof HTMLElement)) return true;
        const st = window.getComputedStyle(el);
        if (st.display === "none" || st.visibility === "hidden") return false;
        if (parseFloat(st.opacity) === 0) return false;
        return true;
    }}

    function hasStrongInteractiveSignal(el) {{
        const role = el.getAttribute("role");
        if (role && CLICKABLE_ROLES.has(role)) return true;
        if (el.hasAttribute("onclick") || el.hasAttribute("tabindex")) return true;
        if (el.hasAttribute("data-click") || el.hasAttribute("data-action")) return true;
        if (el.getAttribute("contenteditable") === "true") return true;
        return false;
    }}

    function hasOwnPointerCursor(el) {{
        try {{
            const st = window.getComputedStyle(el);
            if (st.cursor !== "pointer") return false;
            const parent = el.parentElement;
            if (parent) {{
                const pst = window.getComputedStyle(parent);
                if (pst.cursor === "pointer") return false;
            }}
            return true;
        }} catch(e) {{}}
        return false;
    }}

    function hasTextOrContent(el) {{
        const t = el.textContent || "";
        if (t.trim().length > 0) return true;
        if (el.querySelector("img,video,audio,canvas")) return true;
        const ariaLabel = el.getAttribute("aria-label");
        if (ariaLabel && ariaLabel.trim()) return true;
        const title = el.getAttribute("title");
        if (title && title.trim()) return true;
        return false;
    }}

    function isImplicitInteractive(el) {{
        if (hasStrongInteractiveSignal(el)) return true;
        if (hasOwnPointerCursor(el) && hasTextOrContent(el)) return true;
        return false;
    }}

    function walk(node) {{
        if (node.nodeType === Node.TEXT_NODE) {{
            const t = node.textContent.trim();
            return t ? t : null;
        }}
        if (node.nodeType !== Node.ELEMENT_NODE) return null;
        const tag = node.tagName.toLowerCase();
        if (SKIP.has(tag)) return null;
        if (!visible(node)) return null;

        const children = [];
        for (const ch of node.childNodes) {{
            const r = walk(ch);
            if (r !== null) {{
                children.push(r);
            }}
        }}

        const nativeInteractive = INTERACTIVE.has(tag);
        const implicitInteractive = !nativeInteractive && (node instanceof HTMLElement) && isImplicitInteractive(node);
        const keep = KEEP.has(tag) || implicitInteractive;

        if (!keep) {{
            if (children.length === 0) return null;
            if (children.length === 1) return children[0];
            return children;
        }}

        const obj = {{ tag }};
        const isActionable = nativeInteractive || implicitInteractive;
        if (isActionable) {{
            refCounter++;
            const ref = refCounter;
            obj.ref = ref;
            refMap[ref] = node;
        }}

        for (const attr of ["type", "name", "href", "placeholder", "role", "value", "title"]) {{
            const v = node.getAttribute(attr);
            if (v) obj[attr] = v;
        }}
        const ariaLabel = node.getAttribute("aria-label");
        if (ariaLabel) obj.ariaLabel = ariaLabel;

        if (node.disabled) obj.disabled = true;
        if (node.checked) obj.checked = true;
        if (node.selected) obj.selected = true;

        if (children.length === 1 && typeof children[0] === "string") {{
            obj.text = children[0];
        }} else if (children.length > 0) {{
            obj.children = children;
        }}

        return obj;
    }}

    const result = walk(document.body);
    window.__asagentRefMap = refMap;
    return {{ tree: result, refCount: refCounter }};
}}
"""


def _flatten_tree(node: Any, indent: int = 0) -> list[str]:
    """Convert snapshot tree to compact text lines for LLM consumption."""
    if node is None:
        return []
    if isinstance(node, str):
        return [" " * indent + node]
    if isinstance(node, list):
        lines: list[str] = []
        for child in node:
            lines.extend(_flatten_tree(child, indent))
        return lines
    if not isinstance(node, dict):
        return []

    tag = node.get("tag", "?")
    ref = node.get("ref")
    parts = [tag]
    if ref:
        parts[0] = f"[{ref}] {tag}"

    for attr in (
        "type",
        "name",
        "href",
        "role",
        "ariaLabel",
        "placeholder",
        "value",
        "title",
    ):
        val = node.get(attr)
        if val:
            s = str(val)
            if len(s) > 80:
                s = s[:77] + "..."
            parts.append(f'{attr}="{s}"')

    for flag in ("disabled", "checked", "selected"):
        if node.get(flag):
            parts.append(flag)

    header = " " * indent + " ".join(parts)
    text = node.get("text")
    if text:
        if len(text) > 120:
            text = text[:117] + "..."
        header += f": {text}"

    lines = [header]
    children = node.get("children", [])
    for child in children:
        lines.extend(_flatten_tree(child, indent + 2))
    return lines


class AutomationBrowserService:
    """Async Playwright service managing a persistent CDP-connected browser session."""

    def __init__(
        self,
        user_data_dir: Path,
        *,
        headless: bool = False,
        idle_timeout_seconds: float = 300.0,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._idle_timeout_seconds = idle_timeout_seconds
        self._launcher: ChromeCdpLauncher | None = None
        self._playwright: Any | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()
        self._last_active = time.time()
        self._closed = False

    async def _ensure_browser(self) -> Page:
        async with self._lock:
            self._last_active = time.time()
            if self._page is not None and not self._page.is_closed():
                return self._page

            if self._launcher is None or not self._launcher.is_alive():
                browser_info = detect_system_browser()
                if browser_info is None:
                    raise RuntimeError(
                        "No compatible system browser (Google Chrome or Microsoft Edge) was found on this computer."
                    )
                self._launcher = ChromeCdpLauncher(
                    executable=browser_info.executable,
                    user_data_dir=self._user_data_dir,
                    headless=self._headless,
                )
                endpoint = self._launcher.launch()
            else:
                endpoint = self._launcher.endpoint

            if self._playwright is None:
                self._playwright = await async_playwright().start()

            if self._browser is None or not self._browser.is_connected():
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    endpoint
                )

            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = await self._browser.new_context()

            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()

            return self._page

    async def navigate(self, url: str) -> str:
        """Navigate to a URL and return basic page metadata."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        page = await self._ensure_browser()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        status_code = response.status if response else 200
        return json.dumps(
            {
                "url": page.url,
                "title": title,
                "status": status_code,
            },
            ensure_ascii=False,
        )

    async def snapshot(self) -> str:
        """Capture a compact semantic tree of interactive elements with integer refs."""
        page = await self._ensure_browser()
        data = await page.evaluate(_SNAPSHOT_JS)
        tree = data.get("tree")
        lines = _flatten_tree(tree)
        title = await page.title()
        url = page.url
        header = f"Page: {title} ({url})\n"
        body = "\n".join(lines) if lines else "(Empty page content)"
        return header + body

    async def click(self, ref: int | None = None, selector: str | None = None) -> str:
        """Click an element by [ref] index or CSS selector."""
        page = await self._ensure_browser()
        if ref is not None:
            clicked = await page.evaluate(
                """(ref) => {
                    const el = window.__asagentRefMap && window.__asagentRefMap[ref];
                    if (!el) return false;
                    el.scrollIntoView({ behavior: 'instant', block: 'center' });
                    el.click();
                    return true;
                }""",
                ref,
            )
            if not clicked:
                raise ValueError(
                    f"Interactive element with [ref={ref}] not found. Take a new snapshot first."
                )
            return f"Clicked element [{ref}]."
        if selector:
            await page.click(selector, timeout=10000)
            return f"Clicked selector '{selector}'."
        raise ValueError("Either ref or selector must be provided.")

    async def fill(
        self, text: str, ref: int | None = None, selector: str | None = None
    ) -> str:
        """Fill text into an input or textarea element."""
        page = await self._ensure_browser()
        if ref is not None:
            filled = await page.evaluate(
                """([ref, val]) => {
                    const el = window.__asagentRefMap && window.__asagentRefMap[ref];
                    if (!el) return false;
                    el.scrollIntoView({ behavior: 'instant', block: 'center' });
                    el.focus();
                    if ('value' in el) {
                        el.value = val;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    } else {
                        el.textContent = val;
                    }
                    return true;
                }""",
                [ref, text],
            )
            if not filled:
                raise ValueError(
                    f"Interactive element with [ref={ref}] not found. Take a new snapshot first."
                )
            return f"Filled text into element [{ref}]."
        if selector:
            await page.fill(selector, text, timeout=10000)
            return f"Filled text into selector '{selector}'."
        raise ValueError("Either ref or selector must be provided.")

    async def select(
        self, value: str, ref: int | None = None, selector: str | None = None
    ) -> str:
        """Select a dropdown option by value."""
        page = await self._ensure_browser()
        if ref is not None:
            selected = await page.evaluate(
                """([ref, val]) => {
                    const el = window.__asagentRefMap && window.__asagentRefMap[ref];
                    if (!el || el.tagName.toLowerCase() !== 'select') return false;
                    el.value = val;
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }""",
                [ref, value],
            )
            if not selected:
                raise ValueError(f"Select element with [ref={ref}] not found.")
            return f"Selected option '{value}' on element [{ref}]."
        if selector:
            await page.select_option(selector, value, timeout=10000)
            return f"Selected option '{value}' on selector '{selector}'."
        raise ValueError("Either ref or selector must be provided.")

    async def wait(self, seconds: float = 2.0) -> str:
        """Wait for dynamic content or page updates."""
        bounded = max(0.1, min(seconds, 30.0))
        page = await self._ensure_browser()
        await page.wait_for_timeout(int(bounded * 1000))
        title = await page.title()
        return f"Waited {bounded:.1f}s. Current page: {title} ({page.url})."

    async def read_page(self) -> str:
        """Read visible textual content from the current page."""
        page = await self._ensure_browser()
        title = await page.title()
        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        snippet = text[:20000]
        return f"Page: {title} ({page.url})\n\n{snippet}"

    async def close(self) -> None:
        """Close browser context, Playwright connection, and the Chrome process."""
        async with self._lock:
            self._page = None
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            if self._launcher:
                self._launcher.close()
                self._launcher = None
