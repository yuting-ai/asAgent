import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from asagent.api.auth import LocalApiToken


class LocalApiBootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrowserBridgeBootstrap:
    base_url: str
    token: str


@dataclass(frozen=True, slots=True)
class LocalApiBootstrap:
    token: LocalApiToken
    browser_bridge: BrowserBridgeBootstrap | None = None


def read_local_api_bootstrap(read_line: Callable[[], str]) -> LocalApiBootstrap:
    line = read_line()

    if not line:
        raise LocalApiBootstrapError("local API bootstrap input is missing")

    try:
        payload: Any = json.loads(line)
    except json.JSONDecodeError as error:
        raise LocalApiBootstrapError("local API bootstrap input is invalid") from error

    if not isinstance(payload, dict):
        raise LocalApiBootstrapError("local API bootstrap input is invalid")

    token = payload.get("token")
    if not isinstance(token, str):
        raise LocalApiBootstrapError("local API bootstrap input is invalid")

    try:
        access_token = LocalApiToken(token)
    except ValueError as error:
        raise LocalApiBootstrapError("local API bootstrap input is invalid") from error

    if "browser_bridge" not in payload:
        return LocalApiBootstrap(token=access_token)

    bridge_payload = payload["browser_bridge"]
    if not isinstance(bridge_payload, dict):
        raise LocalApiBootstrapError("local API bootstrap input is invalid")

    base_url = bridge_payload.get("base_url")
    bridge_token = bridge_payload.get("token")
    if not isinstance(base_url, str) or not isinstance(bridge_token, str):
        raise LocalApiBootstrapError("local API bootstrap input is invalid")

    try:
        return LocalApiBootstrap(
            token=access_token,
            browser_bridge=BrowserBridgeBootstrap(
                base_url=_validated_bridge_base_url(base_url),
                token=_validated_bridge_token(bridge_token),
            ),
        )
    except ValueError as error:
        raise LocalApiBootstrapError("local API bootstrap input is invalid") from error


def read_local_api_token(read_line: Callable[[], str]) -> LocalApiToken:
    return read_local_api_bootstrap(read_line).token


def _validated_bridge_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("browser bridge base_url is invalid")
    return f"http://127.0.0.1:{parsed.port}"


def _validated_bridge_token(token: str) -> str:
    if not token or any(character.isspace() for character in token):
        raise ValueError("browser bridge token is invalid")
    return token
