from dataclasses import dataclass
from typing import Any

import httpx

from asagent.tools.errors import SAFE_BROWSER_OPERATION_ERRORS, ToolOperationError


@dataclass(frozen=True, slots=True)
class BrowserPageContent:
    title: str
    url: str
    text: str


@dataclass(frozen=True, slots=True)
class BrowserInteractiveElement:
    target_id: str
    name: str
    role: str
    tag: str
    disabled: bool


@dataclass(frozen=True, slots=True)
class BrowserInteractiveSnapshot:
    url: str
    elements: tuple[BrowserInteractiveElement, ...]


@dataclass(frozen=True, slots=True)
class BrowserClickResult:
    action: str
    url: str
    title: str
    page: BrowserPageContent | None = None


@dataclass(frozen=True, slots=True)
class BrowserWaitResult:
    changed: bool
    page: BrowserPageContent


class BrowserPageBridgeError(RuntimeError):
    """The private Main browser page bridge rejected or failed a request."""


class BrowserPageBridgeClient:
    """Authenticated HTTP adapter for Main's private page bridge."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        http_client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._http_client = http_client
        self._timeout_seconds = timeout_seconds

    async def read_current_page(self, tab_id: str) -> BrowserPageContent:
        payload = await self._post_json(
            "/read-current-page",
            {"tab_id": tab_id},
            failure_message="current browser tab is not visible",
        )
        return _page_content_from_payload(payload)

    async def inspect_interactive(self, tab_id: str) -> BrowserInteractiveSnapshot:
        payload = await self._post_json(
            "/inspect-interactive",
            {"tab_id": tab_id},
            failure_message="current browser tab is not visible",
        )
        return _interactive_snapshot_from_payload(payload)

    async def click_current_page(
        self,
        tab_id: str,
        target_id: str,
    ) -> BrowserClickResult:
        payload = await self._post_json(
            "/click-current-page",
            {"tab_id": tab_id, "target_id": target_id},
            failure_message="target was not found",
        )
        return _click_result_from_payload(payload)

    async def wait_for_current_page(
        self, tab_id: str, seconds: int
    ) -> BrowserWaitResult:
        payload = await self._post_json(
            "/wait-for-current-page",
            {"tab_id": tab_id, "seconds": seconds},
            failure_message="current browser tab is not visible",
            timeout_seconds=float(seconds + 5),
        )
        return _wait_result_from_payload(payload)

    async def _post_json(
        self,
        path: str,
        body: dict[str, object],
        *,
        failure_message: str,
        timeout_seconds: float | None = None,
    ) -> Any:
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient()

        try:
            response = await client.post(
                f"{self._base_url}{path}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=self._timeout_seconds
                if timeout_seconds is None
                else timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise BrowserPageBridgeError(failure_message) from error
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code != 200:
            detail = _detail_from_error_payload(response)
            if detail in SAFE_BROWSER_OPERATION_ERRORS:
                raise ToolOperationError(detail)
            raise BrowserPageBridgeError(failure_message)

        try:
            return response.json()
        except ValueError as error:
            raise BrowserPageBridgeError(failure_message) from error


def _detail_from_error_payload(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    return detail if isinstance(detail, str) else None


def _page_content_from_payload(payload: object) -> BrowserPageContent:
    if not isinstance(payload, dict):
        raise BrowserPageBridgeError("current browser tab is not visible")

    title = payload.get("title")
    url = payload.get("url")
    text = payload.get("text")
    if (
        not isinstance(title, str)
        or not isinstance(url, str)
        or not isinstance(text, str)
    ):
        raise BrowserPageBridgeError("current browser tab is not visible")

    return BrowserPageContent(title=title, url=url, text=text)


def _interactive_snapshot_from_payload(payload: object) -> BrowserInteractiveSnapshot:
    if not isinstance(payload, dict):
        raise BrowserPageBridgeError("current browser tab is not visible")

    url = payload.get("url")
    elements_payload = payload.get("elements")
    if not isinstance(url, str) or not isinstance(elements_payload, list):
        raise BrowserPageBridgeError("current browser tab is not visible")

    elements: list[BrowserInteractiveElement] = []
    for item in elements_payload:
        if not isinstance(item, dict):
            continue
        target_id = item.get("target_id")
        name = item.get("name")
        role = item.get("role")
        tag = item.get("tag")
        disabled = item.get("disabled")
        if (
            not isinstance(target_id, str)
            or not isinstance(name, str)
            or not isinstance(role, str)
            or not isinstance(tag, str)
            or not isinstance(disabled, bool)
        ):
            continue
        elements.append(
            BrowserInteractiveElement(
                target_id=target_id,
                name=name,
                role=role,
                tag=tag,
                disabled=disabled,
            )
        )

    return BrowserInteractiveSnapshot(url=url, elements=tuple(elements))


def _click_result_from_payload(payload: object) -> BrowserClickResult:
    if not isinstance(payload, dict):
        raise BrowserPageBridgeError("target was not found")

    action = payload.get("action")
    url = payload.get("url")
    title = payload.get("title")
    if (
        not isinstance(action, str)
        or not isinstance(url, str)
        or not isinstance(title, str)
    ):
        raise BrowserPageBridgeError("target was not found")

    page_payload = payload.get("page")
    page = None
    if page_payload is not None:
        try:
            page = _page_content_from_payload(page_payload)
        except BrowserPageBridgeError as error:
            raise BrowserPageBridgeError("target was not found") from error

    return BrowserClickResult(action=action, url=url, title=title, page=page)


def _wait_result_from_payload(payload: object) -> BrowserWaitResult:
    if not isinstance(payload, dict):
        raise BrowserPageBridgeError("current browser tab is not visible")

    changed = payload.get("changed")
    page_payload = payload.get("page")
    if not isinstance(changed, bool):
        raise BrowserPageBridgeError("current browser tab is not visible")

    try:
        page = _page_content_from_payload(page_payload)
    except BrowserPageBridgeError as error:
        raise BrowserPageBridgeError("current browser tab is not visible") from error

    return BrowserWaitResult(changed=changed, page=page)
