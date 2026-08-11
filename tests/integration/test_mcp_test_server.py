import asyncio
import json
import sys
from pathlib import Path
from typing import Final

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_PROTOCOL_VERSION: Final = "2026-07-28"
_REQUEST_METADATA: Final = {
    "io.modelcontextprotocol/protocolVersion": _PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientInfo": {
        "name": "asagent-test-client",
        "version": "0.1.0",
    },
    "io.modelcontextprotocol/clientCapabilities": {},
}


async def _start_server() -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        str(_SERVER_PATH),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


async def _send(
    process: asyncio.subprocess.Process,
    *,
    request_id: int,
    method: str,
    params: dict[str, object],
) -> None:
    assert process.stdin is not None

    request_params = {**params, "_meta": _REQUEST_METADATA}
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }
    process.stdin.write(json.dumps(payload).encode() + b"\n")
    await process.stdin.drain()


async def _read_response(process: asyncio.subprocess.Process) -> dict[str, object]:
    assert process.stdout is not None

    line = await asyncio.wait_for(process.stdout.readline(), timeout=2.0)
    assert line
    response: object = json.loads(line)
    assert isinstance(response, dict)
    return response


async def _stop(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return

    assert process.stdin is not None
    process.stdin.close()

    try:
        await asyncio.wait_for(process.wait(), timeout=2.0)
    except TimeoutError:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=2.0)


async def test_modern_mcp_test_server_discovers_lists_and_calls_tools() -> None:
    process = await _start_server()

    try:
        assert process.stderr is not None
        startup_log = await asyncio.wait_for(process.stderr.readline(), timeout=2.0)
        assert startup_log.decode().strip() == "asagent MCP test server started"

        await _send(
            process,
            request_id=1,
            method="server/discover",
            params={},
        )
        assert await _read_response(process) == {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "resultType": "complete",
                "supportedVersions": [_PROTOCOL_VERSION],
                "capabilities": {"tools": {}},
                "_meta": {
                    "io.modelcontextprotocol/serverInfo": {
                        "name": "asagent-test-server",
                        "version": "0.1.0",
                    },
                },
                "instructions": "Use the add tool to add two numbers.",
                "ttlMs": 60_000,
                "cacheScope": "public",
            },
        }

        await _send(
            process,
            request_id=2,
            method="tools/list",
            params={},
        )
        listed = await _read_response(process)
        assert listed["id"] == 2
        assert listed["result"] == {
            "resultType": "complete",
            "tools": [
                {
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
                },
            ],
            "ttlMs": 60_000,
            "cacheScope": "public",
        }

        await _send(
            process,
            request_id=3,
            method="tools/call",
            params={
                "name": "add",
                "arguments": {"left": 2, "right": 3},
            },
        )
        assert await _read_response(process) == {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {
                "resultType": "complete",
                "content": [{"type": "text", "text": "5"}],
                "isError": False,
            },
        }
    finally:
        await _stop(process)


async def test_mcp_test_server_keeps_protocol_and_tool_errors_distinct() -> None:
    process = await _start_server()

    try:
        assert process.stdin is not None
        process.stdin.write(b"{not json}\n")
        await process.stdin.drain()
        assert await _read_response(process) == {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": "Parse error",
            },
        }

        await _send(
            process,
            request_id=4,
            method="tools/call",
            params={
                "name": "add",
                "arguments": {"left": "two", "right": 3},
            },
        )
        assert await _read_response(process) == {
            "jsonrpc": "2.0",
            "id": 4,
            "result": {
                "resultType": "complete",
                "content": [
                    {
                        "type": "text",
                        "text": "left and right must both be numbers",
                    },
                ],
                "isError": True,
            },
        }

        await _send(
            process,
            request_id=5,
            method="tools/call",
            params={
                "name": "missing",
                "arguments": {},
            },
        )
        assert await _read_response(process) == {
            "jsonrpc": "2.0",
            "id": 5,
            "error": {
                "code": -32602,
                "message": "Unknown tool: missing",
            },
        }
    finally:
        await _stop(process)
