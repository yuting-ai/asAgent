import json
import os
import sys
from collections.abc import Mapping
from typing import Final, TypeGuard

_PROTOCOL_VERSION: Final = "2026-07-28"
_SERVER_INFO: Final = {
    "name": "asagent-test-server",
    "version": "0.1.0",
}
_REQUEST_METADATA_KEYS: Final = {
    "io.modelcontextprotocol/protocolVersion",
    "io.modelcontextprotocol/clientInfo",
    "io.modelcontextprotocol/clientCapabilities",
}
_ADD_TOOL: Final = {
    "name": "add",
    "title": "Add numbers",
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


def main() -> None:
    if os.environ.get("ASAGENT_TEST_MCP_PARENT_SECRET") is not None:
        raise RuntimeError("MCP server inherited a parent secret")

    print("asagent MCP test server started", file=sys.stderr, flush=True)

    for line in sys.stdin:
        response = _handle_line(line)
        print(
            json.dumps(response, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )


def _handle_line(line: str) -> dict[str, object]:
    try:
        payload: object = json.loads(line)
    except json.JSONDecodeError:
        return _error(None, -32700, "Parse error")

    request = _as_object(payload)
    if request is None or request.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")

    request_id = request.get("id")
    method = request.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request")

    params = _as_object(request.get("params"))
    if params is None:
        return _error(request_id, -32602, "params must be an object")

    metadata_error = _validate_metadata(params, request_id)
    if metadata_error is not None:
        return metadata_error

    if method == "server/discover":
        return _discover(request_id, params)
    if method == "tools/list":
        return _list_tools(request_id, params)
    if method == "tools/call":
        return _call_tool(request_id, params)

    return _error(request_id, -32601, f"Method not found: {method}")


def _discover(
    request_id: object,
    params: Mapping[str, object],
) -> dict[str, object]:
    if set(params) != {"_meta"}:
        return _error(request_id, -32602, "server/discover accepts only _meta")

    return _result(
        request_id,
        {
            "resultType": "complete",
            "supportedVersions": [_PROTOCOL_VERSION],
            "capabilities": {"tools": {}},
            "_meta": {"io.modelcontextprotocol/serverInfo": _SERVER_INFO},
            "instructions": "Use the add tool to add two numbers.",
            "ttlMs": 60_000,
            "cacheScope": "public",
        },
    )


def _list_tools(
    request_id: object,
    params: Mapping[str, object],
) -> dict[str, object]:
    unexpected = set(params) - {"_meta", "cursor"}
    if unexpected:
        return _error(request_id, -32602, "tools/list received unknown parameters")
    if params.get("cursor") is not None:
        return _error(request_id, -32602, "tools/list has no additional pages")

    return _result(
        request_id,
        {
            "resultType": "complete",
            "tools": [_ADD_TOOL],
            "ttlMs": 60_000,
            "cacheScope": "public",
        },
    )


def _call_tool(
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
                "resultType": "complete",
                "content": [
                    {
                        "type": "text",
                        "text": "left and right must both be numbers",
                    },
                ],
                "isError": True,
            },
        )

    total = left + right
    return _result(
        request_id,
        {
            "resultType": "complete",
            "content": [{"type": "text", "text": str(total)}],
            "isError": False,
        },
    )


def _validate_metadata(
    params: Mapping[str, object],
    request_id: object,
) -> dict[str, object] | None:
    metadata = _as_object(params.get("_meta"))
    if metadata is None or set(metadata) != _REQUEST_METADATA_KEYS:
        return _error(request_id, -32602, "Missing or invalid MCP request metadata")

    if metadata["io.modelcontextprotocol/protocolVersion"] != _PROTOCOL_VERSION:
        return _error(request_id, -32602, "Unsupported protocol version")

    client_info = _as_object(metadata["io.modelcontextprotocol/clientInfo"])
    client_capabilities = _as_object(
        metadata["io.modelcontextprotocol/clientCapabilities"],
    )
    if client_info is None or client_capabilities is None:
        return _error(request_id, -32602, "Missing or invalid MCP request metadata")
    if not isinstance(client_info.get("name"), str):
        return _error(request_id, -32602, "Missing or invalid MCP request metadata")
    if not isinstance(client_info.get("version"), str):
        return _error(request_id, -32602, "Missing or invalid MCP request metadata")

    return None


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
