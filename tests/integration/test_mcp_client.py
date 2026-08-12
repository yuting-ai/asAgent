import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.tools.mcp import (
    McpClient,
    McpProtocolError,
    McpRemoteError,
    McpToolDescription,
)

_SERVER_PATH: Final = Path(__file__).parents[1] / "fixtures" / "mcp_test_server.py"
_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_SERVER_PATH),
)
_LEGACY_SERVER_PATH: Final = (
    Path(__file__).parents[1] / "fixtures" / "mcp_legacy_test_server.py"
)
_LEGACY_SERVER_COMMAND: Final = (
    sys.executable,
    "-u",
    str(_LEGACY_SERVER_PATH),
)
_OMIT_IS_ERROR_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--omit-is-error",
)
_INVALID_IS_ERROR_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--invalid-is-error",
)


@pytest.mark.asyncio
async def test_client_discovers_lists_and_calls_modern_mcp_tools() -> None:
    client = McpClient(command=_SERVER_COMMAND)

    try:
        server = await client.start()

        assert server.protocol_version == "2026-07-28"
        assert server.name == "asagent-test-server"
        assert server.version == "0.1.0"
        assert server.supports_tools is True
        assert server.instructions == "Use the add tool to add two numbers."

        assert await client.list_tools() == (
            McpToolDescription(
                name="add",
                title="Add numbers",
                description="Add two numbers.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "left": {"type": "number"},
                        "right": {"type": "number"},
                    },
                    "required": ["left", "right"],
                },
            ),
        )

        result = await client.call_tool(
            name="add",
            arguments={"left": 2, "right": 3},
        )

        assert result.text_content == ("5",)
        assert result.is_error is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_raises_for_mcp_protocol_errors() -> None:
    client = McpClient(command=_SERVER_COMMAND)

    try:
        await client.start()

        with pytest.raises(McpRemoteError, match="Unknown tool: missing"):
            await client.call_tool(name="missing", arguments={})
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_restarts_with_legacy_stdio_lifecycle() -> None:
    client = McpClient(command=_LEGACY_SERVER_COMMAND)

    try:
        server = await client.start()

        assert server.protocol_version == "2025-11-25"
        assert server.name == "asagent-legacy-test-server"
        assert server.supports_tools is True
        assert server.instructions == "Use the add tool to add two numbers."

        assert await client.list_tools() == (
            McpToolDescription(
                name="add",
                title=None,
                description="Add two numbers.",
                input_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "left": {"type": "number"},
                        "right": {"type": "number"},
                    },
                    "required": ["left", "right"],
                },
            ),
        )

        result = await client.call_tool(
            name="add",
            arguments={"left": 20, "right": 22},
        )

        assert result.text_content == ("42",)
        assert result.is_error is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_treats_missing_is_error_as_success() -> None:
    client = McpClient(command=_OMIT_IS_ERROR_SERVER_COMMAND)

    try:
        await client.start()

        result = await client.call_tool(
            name="add",
            arguments={"left": 1, "right": 2},
        )

        assert result.text_content == ("3",)
        assert result.is_error is False
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_rejects_non_boolean_is_error() -> None:
    client = McpClient(command=_INVALID_IS_ERROR_SERVER_COMMAND)

    try:
        await client.start()

        with pytest.raises(McpProtocolError, match="invalid isError"):
            await client.call_tool(
                name="add",
                arguments={"left": 1, "right": 2},
            )
    finally:
        await client.aclose()
