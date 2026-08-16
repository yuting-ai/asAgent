from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class BrowserPageContent:
    title: str
    url: str
    text: str


class BrowserPageBridgeError(RuntimeError):
    """The private Main browser page bridge rejected or failed a read."""


class BrowserPageBridgeClient:
    """Authenticated HTTP adapter for Main's private page-read bridge."""

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
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient()

        try:
            response = await client.post(
                f"{self._base_url}/read-current-page",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                json={"tab_id": tab_id},
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as error:
            raise BrowserPageBridgeError(
                "current browser page could not be read",
            ) from error
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code != 200:
            raise BrowserPageBridgeError(
                "current browser page could not be read",
            )

        try:
            payload: Any = response.json()
        except ValueError as error:
            raise BrowserPageBridgeError(
                "current browser page could not be read",
            ) from error

        return _page_content_from_payload(payload)


def _page_content_from_payload(payload: object) -> BrowserPageContent:
    if not isinstance(payload, dict):
        raise BrowserPageBridgeError("current browser page could not be read")

    title = payload.get("title")
    url = payload.get("url")
    text = payload.get("text")
    if (
        not isinstance(title, str)
        or not isinstance(url, str)
        or not isinstance(text, str)
    ):
        raise BrowserPageBridgeError("current browser page could not be read")

    return BrowserPageContent(title=title, url=url, text=text)
