import json
from collections.abc import Callable
from typing import Any

from asagent.api.auth import LocalApiToken


class LocalApiBootstrapError(ValueError):
    pass


def read_local_api_token(read_line: Callable[[], str]) -> LocalApiToken:
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
        return LocalApiToken(token)
    except ValueError as error:
        raise LocalApiBootstrapError("local API bootstrap input is invalid") from error
