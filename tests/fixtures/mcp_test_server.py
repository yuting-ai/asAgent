import json
import os
import sys
import time
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
_EXPECTED_CREDENTIAL_ENVIRONMENT = "ASAGENT_TEST_MCP_CREDENTIAL"
_EXPECTED_CREDENTIAL = "test-connection-credential"
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
_MULTIPLY_TOOL: Final = {
    "name": "multiply",
    "title": "Multiply numbers",
    "description": "Multiply two numbers.",
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

    if "--require-credential" in sys.argv:
        if os.environ.get(_EXPECTED_CREDENTIAL_ENVIRONMENT) != _EXPECTED_CREDENTIAL:
            raise RuntimeError("MCP server credential was not supplied")

    if "--reject-credential" in sys.argv:
        if os.environ.get(_EXPECTED_CREDENTIAL_ENVIRONMENT) is not None:
            raise RuntimeError("MCP server received another server credential")

    print("asagent MCP test server started", file=sys.stderr, flush=True)

    for line in sys.stdin:
        response = _handle_line(line)
        responses = response if isinstance(response, tuple) else (response,)
        for item in responses:
            print(
                json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                flush=True,
            )


def _handle_line(line: str) -> dict[str, object] | tuple[dict[str, object], ...]:
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
    if method == "subscriptions/listen":
        return _listen(request_id, params)

    return _error(request_id, -32601, f"Method not found: {method}")


def _tool_capabilities() -> dict[str, object]:
    if "--emit-tool-list-change" in sys.argv:
        return {"listChanged": True}
    return {}


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
            "capabilities": {"tools": _tool_capabilities()},
            "_meta": {"io.modelcontextprotocol/serverInfo": _SERVER_INFO},
            "instructions": "Use the add tool to add two numbers.",
            "ttlMs": 60_000,
            "cacheScope": "public",
        },
    )


def _tool_list_result(
    request_id: object,
    *,
    tools: list[Mapping[str, object]],
    next_cursor: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "resultType": "complete",
        "tools": tools,
        "ttlMs": 60_000,
        "cacheScope": "public",
    }
    if next_cursor is not None:
        result["nextCursor"] = next_cursor
    return _result(request_id, result)


def _list_tools(
    request_id: object,
    params: Mapping[str, object],
) -> dict[str, object]:
    unexpected = set(params) - {"_meta", "cursor"}
    if unexpected:
        return _error(request_id, -32602, "tools/list received unknown parameters")

    cursor = params.get("cursor")

    if "--paginate-tools" in sys.argv:
        if cursor is None:
            return _tool_list_result(
                request_id,
                tools=[_ADD_TOOL],
                next_cursor="",
            )
        if cursor == "":
            return _tool_list_result(
                request_id,
                tools=[_MULTIPLY_TOOL],
            )
        return _error(request_id, -32602, "invalid tools/list cursor")

    if "--repeat-tools-cursor" in sys.argv:
        return _tool_list_result(
            request_id,
            tools=[_ADD_TOOL],
            next_cursor="repeated-cursor",
        )

    if "--endless-tool-pages" in sys.argv:
        if cursor is None:
            next_cursor = "1"
        elif isinstance(cursor, str) and cursor.isdigit():
            next_cursor = str(int(cursor) + 1)
        else:
            return _error(request_id, -32602, "invalid tools/list cursor")
        return _tool_list_result(
            request_id,
            tools=[],
            next_cursor=next_cursor,
        )

    if "--fail-tool-list-on-refresh" in sys.argv and _tools_changed_emitted:
        return _error(request_id, -32603, "tools/list failed dynamically on refresh")

    if "--hang-tool-list-on-refresh" in sys.argv and _tools_changed_emitted:
        time.sleep(3600)

    if cursor is not None:
        return _error(request_id, -32602, "tools/list has no additional pages")

    return _tool_list_result(
        request_id,
        tools=_listed_tools(),
    )


_tools_changed_emitted = False


def _listed_tools() -> list[Mapping[str, object]]:
    tools: list[Mapping[str, object]] = [_ADD_TOOL]
    if "--expose-multiply" in sys.argv or _tools_changed_emitted:
        tools.append(_MULTIPLY_TOOL)
    return tools


def _call_tool(
    request_id: object,
    params: Mapping[str, object],
) -> dict[str, object]:
    name = params.get("name")
    arguments = _as_object(params.get("arguments"))
    if not isinstance(name, str) or arguments is None:
        return _error(request_id, -32602, "tools/call requires name and arguments")

    if name != "add":
        if name == "multiply":
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

            product = left * right
            return _result(
                request_id,
                {
                    "resultType": "complete",
                    "content": [{"type": "text", "text": str(product)}],
                    "isError": False,
                },
            )

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
    return _tool_call_success_result(request_id, str(total))


def _tool_call_success_result(
    request_id: object,
    text: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "resultType": "complete",
        "content": [{"type": "text", "text": text}],
    }

    if "--invalid-is-error" in sys.argv:
        payload["isError"] = "not-a-bool"
    elif "--omit-is-error" not in sys.argv:
        payload["isError"] = False

    return _result(request_id, payload)


def _listen(
    request_id: object,
    params: Mapping[str, object],
) -> dict[str, object] | tuple[dict[str, object], ...]:
    if "--emit-tool-list-change" not in sys.argv:
        return _error(
            request_id,
            -32602,
            "subscriptions/listen is not supported without --emit-tool-list-change",
        )

    unexpected = set(params) - {"_meta", "notifications"}
    if unexpected:
        return _error(
            request_id,
            -32602,
            "subscriptions/listen received unknown parameters",
        )

    notifications = _as_object(params.get("notifications"))
    if notifications != {"toolsListChanged": True}:
        return _error(
            request_id,
            -32602,
            "subscriptions/listen requires notifications.toolsListChanged=True",
        )

    sub_id = 9999 if "--wrong-subscription-id" in sys.argv else request_id

    acknowledged: dict[str, object] = {
        "jsonrpc": "2.0",
        "method": "notifications/subscriptions/acknowledged",
        "params": {
            "notifications": {"toolsListChanged": True},
            "_meta": {
                "io.modelcontextprotocol/subscriptionId": sub_id,
            },
        },
    }
    changed: dict[str, object] = {
        "jsonrpc": "2.0",
        "method": "notifications/tools/list_changed",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/subscriptionId": sub_id,
            },
        },
    }
    completed: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "resultType": "complete",
            "_meta": {
                "io.modelcontextprotocol/subscriptionId": sub_id,
            },
        },
    }

    global _tools_changed_emitted
    _tools_changed_emitted = True

    if "--change-before-ack" in sys.argv:
        return (changed, acknowledged, completed)

    if "--keep-subscription-open" in sys.argv:
        return (acknowledged, changed)

    if "--burst-tool-list-change" in sys.argv:
        return (acknowledged, changed, changed, changed, completed)

    if "--close-after-ack" in sys.argv:
        # We print acknowledged then exit
        print(
            json.dumps(acknowledged, ensure_ascii=False, separators=(",", ":")),
            flush=True,
        )
        sys.exit(0)

    return (acknowledged, changed, completed)


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
