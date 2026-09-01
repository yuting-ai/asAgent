import asyncio
import gc
import sys
from pathlib import Path
from typing import Final

import pytest

from asagent.tools.mcp import (
    McpClient,
    McpProtocolError,
    McpRemoteError,
    McpRequestTimeoutError,
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
_PAGINATED_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--paginate-tools",
)
_REPEATING_CURSOR_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--repeat-tools-cursor",
)
_ENDLESS_PAGES_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--endless-tool-pages",
)
_SUBSCRIBE_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
)
_CHANGE_BEFORE_ACK_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
    "--change-before-ack",
)
_WRONG_SUB_ID_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
    "--wrong-subscription-id",
)
_BURST_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
    "--burst-tool-list-change",
)
_CLOSE_AFTER_ACK_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
    "--close-after-ack",
)
_HANG_TOOL_LIST_ON_REFRESH_SERVER_COMMAND: Final = (
    *_SERVER_COMMAND,
    "--emit-tool-list-change",
    "--hang-tool-list-on-refresh",
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


@pytest.mark.asyncio
async def test_client_lists_tools_from_all_pages() -> None:
    client = McpClient(command=_PAGINATED_SERVER_COMMAND)
    try:
        await client.start()
        tools = await client.list_tools()
        assert tuple(tool.name for tool in tools) == ("add", "multiply")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_rejects_repeated_tools_list_cursor() -> None:
    client = McpClient(command=_REPEATING_CURSOR_SERVER_COMMAND)
    try:
        await client.start()
        with pytest.raises(McpProtocolError, match="repeated nextCursor"):
            await client.list_tools()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_limits_tools_list_pages() -> None:
    client = McpClient(command=_ENDLESS_PAGES_SERVER_COMMAND)
    try:
        await client.start()
        with pytest.raises(McpProtocolError, match="maximum page count"):
            await client.list_tools()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_supports_concurrent_requests_and_subscriptions() -> None:
    client = McpClient(command=_SUBSCRIBE_SERVER_COMMAND)
    tools_changed_event = asyncio.Event()

    async def _on_changed() -> None:
        tools_changed_event.set()

    try:
        server = await client.start()
        assert server.supports_tool_list_changed is True

        # Initial list before subscription
        initial_tools = await client.list_tools()
        assert tuple(tool.name for tool in initial_tools) == ("add",)

        await client.start_tool_list_subscription(_on_changed)
        await asyncio.wait_for(tools_changed_event.wait(), timeout=2.0)

        # After change notification, tools list should now contain multiply
        updated_tools = await client.list_tools()
        assert tuple(tool.name for tool in updated_tools) == ("add", "multiply")

        # Concurrent calls still route correctly by request_id
        res1, res2 = await asyncio.gather(
            client.call_tool(name="add", arguments={"left": 10, "right": 20}),
            client.call_tool(name="multiply", arguments={"left": 3, "right": 4}),
        )
        assert res1.text_content == ("30",)
        assert res2.text_content == ("12",)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_subscription_fails_if_change_before_ack() -> None:
    client = McpClient(command=_CHANGE_BEFORE_ACK_SERVER_COMMAND)
    tools_changed_event = asyncio.Event()

    async def _on_changed() -> None:
        tools_changed_event.set()

    try:
        await client.start()
        with pytest.raises(
            McpProtocolError, match="emitted tools/list_changed before acknowledgment"
        ):
            await client.start_tool_list_subscription(_on_changed)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_subscription_fails_for_wrong_subscription_id() -> None:
    client = McpClient(command=_WRONG_SUB_ID_SERVER_COMMAND)
    tools_changed_event = asyncio.Event()

    async def _on_changed() -> None:
        tools_changed_event.set()

    try:
        await client.start()
        with pytest.raises(
            McpProtocolError, match="unexpected subscription acknowledgment"
        ):
            await client.start_tool_list_subscription(_on_changed)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_collapses_burst_list_change_notifications() -> None:
    client = McpClient(command=_BURST_SERVER_COMMAND)
    call_count = 0
    changed_event = asyncio.Event()

    async def _on_changed() -> None:
        nonlocal call_count
        call_count += 1
        changed_event.set()

    try:
        await client.start()
        await client.start_tool_list_subscription(_on_changed)
        await asyncio.wait_for(changed_event.wait(), timeout=2.0)
        # The three consecutive server notifications are one refresh burst.
        await asyncio.sleep(0.05)
        assert call_count == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_handles_server_close_after_ack() -> None:
    client = McpClient(command=_CLOSE_AFTER_ACK_SERVER_COMMAND)
    changed_event = asyncio.Event()

    async def _on_changed() -> None:
        changed_event.set()

    try:
        await client.start()
        await client.start_tool_list_subscription(_on_changed)
        with pytest.raises(
            McpProtocolError, match="(closed stdout|transport is broken)"
        ):
            await client.list_tools()
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_client_subscription_cleans_up_worker_after_final_response() -> None:
    client = McpClient(command=_SUBSCRIBE_SERVER_COMMAND)
    changed_event = asyncio.Event()

    async def _on_changed() -> None:
        changed_event.set()

    try:
        await client.start()
        await client.start_tool_list_subscription(_on_changed)
        await asyncio.wait_for(changed_event.wait(), timeout=2.0)

        for _ in range(50):
            if client._subscription_worker_task is None:
                break
            await asyncio.sleep(0.02)

        assert client._subscription_worker_task is None
        assert client._subscription_id is None

        changed_event.clear()
        await client.start_tool_list_subscription(_on_changed)
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("keep_subscription_open", [False, True])
async def test_client_subscription_worker_handles_timeout_and_self_close(
    keep_subscription_open: bool,
) -> None:
    command: tuple[str, ...] = _HANG_TOOL_LIST_ON_REFRESH_SERVER_COMMAND
    if keep_subscription_open:
        command = (*command, "--keep-subscription-open")
    client = McpClient(
        command=command,
        request_timeout_seconds=0.2,
    )
    refresh_failed_event = asyncio.Event()

    async def _on_changed() -> None:
        try:
            await client.list_tools()
        except McpRequestTimeoutError:
            refresh_failed_event.set()

    try:
        await client.start()
        process = client._process
        assert process is not None

        await client.start_tool_list_subscription(_on_changed)
        worker = client._subscription_worker_task
        reader = client._reader_task
        listener = client._subscription_listen_task
        assert worker is not None and reader is not None and listener is not None
        await asyncio.wait_for(refresh_failed_event.wait(), timeout=5.0)
        await asyncio.wait_for(
            asyncio.gather(worker, reader, listener, return_exceptions=True),
            timeout=1.0,
        )

        assert client._process is None
        assert worker.done() and reader.done() and listener.done()
        assert not client._pending_requests
        assert client._subscription_queue.empty()
        await asyncio.wait_for(client._subscription_queue.join(), timeout=1.0)
        assert process.returncode is not None
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("queued_change", [False, True])
@pytest.mark.parametrize("keep_subscription_open", [False, True])
async def test_client_closes_open_subscription_during_refresh(
    queued_change: bool,
    keep_subscription_open: bool,
) -> None:
    command: tuple[str, ...] = _SUBSCRIBE_SERVER_COMMAND
    if keep_subscription_open:
        command = (*command, "--keep-subscription-open")
    client = McpClient(command=command)
    refreshing = asyncio.Event()
    release_refresh = asyncio.Event()

    async def _on_changed() -> None:
        refreshing.set()
        await release_refresh.wait()

    try:
        await client.start()
        process = client._process
        assert process is not None
        await client.start_tool_list_subscription(_on_changed)
        worker = client._subscription_worker_task
        listener = client._subscription_listen_task
        reader = client._reader_task
        assert worker is not None and listener is not None and reader is not None
        await asyncio.wait_for(refreshing.wait(), timeout=1.0)
        if queued_change:
            # Deterministically reproduce another notification arriving while
            # the first callback is blocked, without depending on OS scheduling.
            client._subscription_queue.put_nowait(None)

        await asyncio.wait_for(client.aclose(), timeout=5.0)

        assert worker.done() and listener.done() and reader.done()
        assert process.returncode is not None
        assert client._process is None
        assert not client._pending_requests
        assert client._subscription_queue.empty()
        await asyncio.wait_for(client._subscription_queue.join(), timeout=1.0)
        await client.aclose()
    finally:
        release_refresh.set()
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command", [_CHANGE_BEFORE_ACK_SERVER_COMMAND, _WRONG_SUB_ID_SERVER_COMMAND]
)
async def test_failed_subscription_consumes_all_future_errors(
    command: tuple[str, ...],
) -> None:
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    errors: list[str] = []
    loop.set_exception_handler(lambda _, context: errors.append(str(context)))
    client = McpClient(command=command)

    async def _on_changed() -> None:
        pytest.fail("Invalid subscription must not dispatch changes")

    try:
        await client.start()
        with pytest.raises(McpProtocolError):
            await client.start_tool_list_subscription(_on_changed)
        await client.aclose()
        gc.collect()
        assert errors == []
    finally:
        await client.aclose()
        loop.set_exception_handler(previous_handler)
