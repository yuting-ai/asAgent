import json
import sys
from collections.abc import Mapping
from typing import Final, TypeGuard

_PROTOCOL_VERSION: Final = "2025-11-25"
_SERVER_INFO: Final = {
    "name": "asagent-legacy-test-server",
    "version": "0.1.0",
}
_ADD_TOOL: Final = {
    "name": "add",
    "description": "Add two numbers.",
    "inputSchema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "left": {"type": "number"},
            "right": {"type": "number"},
        },
        "required": ["left", "right"],
    },
}


class LegacyMcpTestServer:
    def __init__(self) -> None:
        self._initialized = False
        self._ready = False

    def handle(
        self,
        line: str,
    ) -> tuple[dict[str, object] | None, bool]:
        try:
            payload: object = json.loads(line)
        except json.JSONDecodeError:
            return _error(None, -32700, "Parse error"), False

        request = _as_object(payload)
        if request is None or request.get("jsonrpc") != "2.0":
            return _error(None, -32600, "Invalid Request"), False

        request_id = request.get("id")
        method = request.get("method")
        params = _as_object(request.get("params"))
        if not isinstance(method, str) or params is None:
            return _error(request_id, -32600, "Invalid Request"), False

        # The first modern probe intentionally poisons this process.
        # Client success therefore proves it launched a fresh legacy process.
        if method == "server/discover":
            return _error(request_id, -32601, "Method not found"), True

        if method == "initialize":
            return self._initialize(request_id, params), False

        if method == "notifications/initialized":
            return self._initialized_notification(request_id, params), False

        if not self._ready:
            return _error(request_id, -32000, "Server is not initialized"), False

        if method == "tools/list":
            return self._list_tools(request_id, params), False
        if method == "tools/call":
            return self._call_tool(request_id, params), False

        return _error(request_id, -32601, f"Method not found: {method}"), False

    def _initialize(
        self,
        request_id: object,
        params: Mapping[str, object],
    ) -> dict[str, object]:
        client_info = _as_object(params.get("clientInfo"))
        if (
            self._initialized
            or set(params) != {"protocolVersion", "capabilities", "clientInfo"}
            or params.get("protocolVersion") != _PROTOCOL_VERSION
            or params.get("capabilities") != {}
            or client_info is None
            or not isinstance(client_info.get("name"), str)
            or not isinstance(client_info.get("version"), str)
        ):
            return _error(request_id, -32602, "Invalid initialize parameters")

        self._initialized = True
        return _result(
            request_id,
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": _SERVER_INFO,
                "instructions": "Use the add tool to add two numbers.",
            },
        )

    def _initialized_notification(
        self,
        request_id: object,
        params: Mapping[str, object],
    ) -> dict[str, object] | None:
        if request_id is not None or not self._initialized or params != {}:
            return _error(request_id, -32602, "Invalid initialized notification")

        self._ready = True
        return None

    def _list_tools(
        self,
        request_id: object,
        params: Mapping[str, object],
    ) -> dict[str, object]:
        if params != {}:
            return _error(request_id, -32602, "tools/list accepts no parameters")
        return _result(request_id, {"tools": [_ADD_TOOL]})

    def _call_tool(
        self,
        request_id: object,
        params: Mapping[str, object],
    ) -> dict[str, object]:
        name = params.get("name")
        arguments = _as_object(params.get("arguments"))
        if not isinstance(name, str) or arguments is None:
            return _error(request_id, -32602, "tools/call requires name and arguments")
        if name != "add":
            return _error(request_id, -32602, f"Unknown tool: {name}")

        left = arguments.get("left")
        right = arguments.get("right")
        if not _is_number(left) or not _is_number(right):
            return _result(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": "left and right must both be numbers",
                        },
                    ],
                    "isError": True,
                },
            )

        return _result(
            request_id,
            {
                "content": [{"type": "text", "text": str(left + right)}],
                "isError": False,
            },
        )


def main() -> None:
    server = LegacyMcpTestServer()

    for line in sys.stdin:
        response, should_exit = server.handle(line)
        if response is not None:
            print(
                json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                flush=True,
            )
        if should_exit:
            return


def _as_object(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return value


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _result(
    request_id: object,
    result: Mapping[str, object],
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": dict(result),
    }


def _error(
    request_id: object,
    code: int,
    message: str,
) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


if __name__ == "__main__":
    main()
