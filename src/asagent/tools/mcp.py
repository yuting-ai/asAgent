import asyncio
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

from asagent.core.tool_definition import ToolDefinition
from asagent.tools.registry import ToolRegistry

_PROTOCOL_VERSION: Final = "2026-07-28"
_LEGACY_PROTOCOL_VERSION: Final = "2025-11-25"
_DEFAULT_REQUEST_TIMEOUT_SECONDS: Final = 5.0
_CLOSE_TIMEOUT_SECONDS: Final = 2.0
_MCP_TOOL_TIMEOUT_SECONDS: Final = 10.0


class McpClientError(RuntimeError):
    pass


class McpProtocolError(McpClientError):
    pass


class McpRequestTimeoutError(McpClientError):
    pass


class McpRemoteError(McpClientError):
    def __init__(self, *, code: int, message: str) -> None:
        super().__init__(f"MCP server error {code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class McpServerInfo:
    protocol_version: str
    name: str
    version: str
    supports_tools: bool
    instructions: str | None


@dataclass(frozen=True, slots=True)
class McpToolDescription:
    name: str
    title: str | None
    description: str
    input_schema: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class McpToolCallResult:
    text_content: tuple[str, ...]
    is_error: bool


class McpTool:
    """Wraps one remote MCP tool as a host-side Tool for ToolRegistry."""

    def __init__(
        self,
        *,
        client: "McpClient",
        server_name: str,
        description: McpToolDescription,
    ) -> None:
        if not server_name:
            raise ValueError("server_name must not be empty")

        self._client = client
        self._server_name = server_name
        self._description = description
        self._definition = _tool_definition_from(
            server_name=server_name,
            description=description,
        )

    @property
    def definition(self) -> ToolDefinition:
        return self._definition

    async def execute(self, arguments: Mapping[str, object]) -> str:
        result = await self._client.call_tool(
            name=self._description.name,
            arguments=arguments,
        )
        content = "\n".join(result.text_content)

        if result.is_error:
            return f"Error: {content}"

        return content


async def register_mcp_tools(
    registry: ToolRegistry,
    client: "McpClient",
    *,
    server_name: str,
    allowed_tools: tuple[str, ...] | None = None,
) -> None:
    """List tools from a started MCP client and register each as McpTool."""

    if not server_name:
        raise ValueError("server_name must not be empty")

    available_tools = {
        description.name: description for description in await client.list_tools()
    }

    if allowed_tools is None:
        tools_to_register = tuple(available_tools.values())
    else:
        missing_tools = [
            tool_name for tool_name in allowed_tools if tool_name not in available_tools
        ]
        if missing_tools:
            raise ValueError(
                "MCP allowed tool is not exposed by server "
                f"{server_name!r}: {missing_tools[0]!r}",
            )
        tools_to_register = tuple(
            available_tools[tool_name] for tool_name in allowed_tools
        )

    for description in tools_to_register:
        registry.register(
            McpTool(
                client=client,
                server_name=server_name,
                description=description,
            ),
        )


class McpClient:
    def __init__(
        self,
        *,
        command: tuple[str, ...],
        client_name: str = "asagent",
        client_version: str = "0.1.0",
        request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS,
        working_directory: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if not command or any(not part for part in command):
            raise ValueError("MCP server command must not be empty")
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if working_directory is not None and not working_directory.is_absolute():
            raise ValueError("MCP server working_directory must be absolute")
        if environment is not None and any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in environment.items()
        ):
            raise ValueError("MCP server environment must contain strings")

        self._command = command
        self._client_name = client_name
        self._client_version = client_version
        self._request_timeout_seconds = request_timeout_seconds
        self._working_directory = working_directory
        self._environment = {} if environment is None else dict(environment)
        self._process: asyncio.subprocess.Process | None = None
        self._server_info: McpServerInfo | None = None
        self._next_request_id = 1
        self._request_lock = asyncio.Lock()
        self._uses_legacy_protocol = False

    async def start(self) -> McpServerInfo:
        if self._process is not None:
            raise RuntimeError("MCP client is already started")

        await self._start_process()

        try:
            result = await self._request("server/discover", {})
            self._server_info = _parse_server_info(result)
        except McpClientError:
            await self.aclose()
            await self._start_process()

            try:
                result = await self._request(
                    "initialize",
                    {
                        "protocolVersion": _LEGACY_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {
                            "name": self._client_name,
                            "version": self._client_version,
                        },
                    },
                    include_metadata=False,
                )
                self._server_info = _parse_legacy_server_info(result)
                self._uses_legacy_protocol = True
                await self._notify(
                    "notifications/initialized",
                    {},
                )
            except BaseException:
                await self.aclose()
                raise
        except BaseException:
            await self.aclose()
            raise

        return self._server_info

    async def list_tools(self) -> tuple[McpToolDescription, ...]:
        server_info = self._require_server_info()
        if not server_info.supports_tools:
            raise McpProtocolError("MCP server does not declare tools capability")

        result = await self._request(
            "tools/list",
            {},
            include_metadata=not self._uses_legacy_protocol,
        )
        if not self._uses_legacy_protocol and result.get("resultType") != "complete":
            raise McpProtocolError("tools/list did not complete")

        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list):
            raise McpProtocolError("tools/list response has invalid tools")

        return tuple(_parse_tool(raw_tool) for raw_tool in raw_tools)

    async def call_tool(
        self,
        *,
        name: str,
        arguments: Mapping[str, object],
    ) -> McpToolCallResult:
        self._require_server_info()

        result = await self._request(
            "tools/call",
            {
                "name": name,
                "arguments": dict(arguments),
            },
            include_metadata=not self._uses_legacy_protocol,
        )
        if not self._uses_legacy_protocol and result.get("resultType") != "complete":
            raise McpProtocolError("tools/call did not complete")

        raw_content = result.get("content")
        if not isinstance(raw_content, list):
            raise McpProtocolError("tools/call response has invalid content")

        text_content: list[str] = []
        for item in raw_content:
            content_item = _as_object(item)
            if content_item is None or content_item.get("type") != "text":
                raise McpProtocolError(
                    "minimal MCP client only supports text tool content",
                )

            text = content_item.get("text")
            if not isinstance(text, str):
                raise McpProtocolError(
                    "minimal MCP client only supports text tool content",
                )
            text_content.append(text)

        is_error = result.get("isError", False)
        if not isinstance(is_error, bool):
            raise McpProtocolError("tools/call response has invalid isError")

        return McpToolCallResult(
            text_content=tuple(text_content),
            is_error=is_error,
        )

    async def aclose(self) -> None:
        process = self._process
        self._process = None
        self._server_info = None
        self._uses_legacy_protocol = False

        if process is None:
            return

        if process.stdin is not None:
            process.stdin.close()

        try:
            await asyncio.wait_for(process.wait(), timeout=_CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_CLOSE_TIMEOUT_SECONDS)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def _start_process(self) -> None:
        self._next_request_id = 1
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self._working_directory,
            env=self._environment,
        )

    async def _notify(
        self,
        method: str,
        params: Mapping[str, object],
    ) -> None:
        process = self._require_process()
        if process.stdin is None:
            raise McpProtocolError("MCP server stdin is unavailable")

        async with self._request_lock:
            payload = {
                "jsonrpc": "2.0",
                "method": method,
                "params": dict(params),
            }
            process.stdin.write(
                json.dumps(payload, separators=(",", ":")).encode() + b"\n",
            )
            await process.stdin.drain()

    async def _request(
        self,
        method: str,
        params: Mapping[str, object],
        *,
        include_metadata: bool = True,
    ) -> Mapping[str, object]:
        process = self._require_process()
        if process.stdin is None or process.stdout is None:
            raise McpProtocolError("MCP server stdio streams are unavailable")

        async with self._request_lock:
            request_id = self._next_request_id
            self._next_request_id += 1

            request_params = dict(params)
            if include_metadata:
                request_params["_meta"] = self._request_metadata()

            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": request_params,
            }
            process.stdin.write(
                json.dumps(payload, separators=(",", ":")).encode() + b"\n",
            )
            await process.stdin.drain()

            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=self._request_timeout_seconds,
                )
            except TimeoutError as error:
                await self.aclose()
                raise McpRequestTimeoutError(
                    f"MCP request timed out: {method}",
                ) from error

            if not line:
                await self.aclose()
                raise McpProtocolError("MCP server closed stdout unexpectedly")

            return _parse_response(line, request_id)

    def _request_metadata(self) -> dict[str, object]:
        return {
            "io.modelcontextprotocol/protocolVersion": _PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientInfo": {
                "name": self._client_name,
                "version": self._client_version,
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }

    def _require_process(self) -> asyncio.subprocess.Process:
        if self._process is None:
            raise RuntimeError("MCP client is not started")
        return self._process

    def _require_server_info(self) -> McpServerInfo:
        self._require_process()
        if self._server_info is None:
            raise RuntimeError("MCP server discovery has not completed")
        return self._server_info


class McpServerSession:
    """Owns one MCP client process and its one-time tool import."""

    def __init__(
        self,
        *,
        client: McpClient,
        registry: ToolRegistry,
        server_name: str,
        allowed_tools: tuple[str, ...] | None = None,
    ) -> None:
        if not server_name:
            raise ValueError("server_name must not be empty")

        self._client = client
        self._registry = registry
        self._server_name = server_name
        self._allowed_tools = allowed_tools
        self._started = False
        self._closed = False

    async def start(self) -> McpServerInfo:
        if self._closed:
            raise RuntimeError("MCP server session is closed")
        if self._started:
            raise RuntimeError("MCP server session is already started")

        try:
            server_info = await self._client.start()
            await register_mcp_tools(
                self._registry,
                self._client,
                server_name=self._server_name,
                allowed_tools=self._allowed_tools,
            )
        except BaseException:
            await self._client.aclose()
            self._closed = True
            raise

        self._started = True
        return server_info

    async def aclose(self) -> None:
        if self._closed:
            return

        self._closed = True
        await self._client.aclose()


def _parse_response(line: bytes, request_id: int) -> Mapping[str, object]:
    try:
        payload: object = json.loads(line)
    except json.JSONDecodeError as error:
        raise McpProtocolError("MCP server returned invalid JSON") from error

    response = _as_object(payload)
    if response is None or response.get("jsonrpc") != "2.0":
        raise McpProtocolError("MCP server returned an invalid JSON-RPC response")
    if response.get("id") != request_id:
        raise McpProtocolError("MCP server response id does not match request")

    remote_error = _as_object(response.get("error"))
    if remote_error is not None:
        code = remote_error.get("code")
        message = remote_error.get("message")
        if (
            isinstance(code, int)
            and not isinstance(code, bool)
            and isinstance(
                message,
                str,
            )
        ):
            raise McpRemoteError(code=code, message=message)
        raise McpProtocolError("MCP server returned an invalid error response")

    result = _as_object(response.get("result"))
    if result is None:
        raise McpProtocolError("MCP server response has no result")

    return result


def _parse_legacy_server_info(result: Mapping[str, object]) -> McpServerInfo:
    protocol_version = result.get("protocolVersion")
    capabilities = _as_object(result.get("capabilities"))
    raw_server_info = _as_object(result.get("serverInfo"))
    instructions = result.get("instructions")

    if (
        not isinstance(protocol_version, str)
        or not protocol_version
        or capabilities is None
        or raw_server_info is None
    ):
        raise McpProtocolError("initialize response is incomplete")

    name = raw_server_info.get("name")
    version = raw_server_info.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise McpProtocolError("initialize response has invalid server info")
    if instructions is not None and not isinstance(instructions, str):
        raise McpProtocolError("initialize response has invalid instructions")

    return McpServerInfo(
        protocol_version=protocol_version,
        name=name,
        version=version,
        supports_tools=isinstance(capabilities.get("tools"), Mapping),
        instructions=instructions,
    )


def _parse_server_info(result: Mapping[str, object]) -> McpServerInfo:
    if result.get("resultType") != "complete":
        raise McpProtocolError("server/discover did not complete")

    supported_versions = result.get("supportedVersions")
    if (
        not isinstance(supported_versions, list)
        or not all(isinstance(version, str) for version in supported_versions)
        or _PROTOCOL_VERSION not in supported_versions
    ):
        raise McpProtocolError("MCP server does not support the modern protocol")

    capabilities = _as_object(result.get("capabilities"))
    metadata = _as_object(result.get("_meta"))
    if capabilities is None or metadata is None:
        raise McpProtocolError("server/discover response is incomplete")

    raw_server_info = _as_object(
        metadata.get("io.modelcontextprotocol/serverInfo"),
    )
    if raw_server_info is None:
        raise McpProtocolError("server/discover response has no server info")

    name = raw_server_info.get("name")
    version = raw_server_info.get("version")
    instructions = result.get("instructions")
    if not isinstance(name, str) or not isinstance(version, str):
        raise McpProtocolError("server/discover response has invalid server info")
    if instructions is not None and not isinstance(instructions, str):
        raise McpProtocolError("server/discover response has invalid instructions")

    return McpServerInfo(
        protocol_version=_PROTOCOL_VERSION,
        name=name,
        version=version,
        supports_tools=isinstance(capabilities.get("tools"), Mapping),
        instructions=instructions,
    )


def _parse_tool(value: object) -> McpToolDescription:
    tool = _as_object(value)
    if tool is None:
        raise McpProtocolError("tools/list contains an invalid tool")

    name = tool.get("name")
    title = tool.get("title")
    description = tool.get("description")
    input_schema = _as_object(tool.get("inputSchema"))
    if not isinstance(name, str) or not isinstance(description, str):
        raise McpProtocolError("tools/list contains an invalid tool")
    if title is not None and not isinstance(title, str):
        raise McpProtocolError("tools/list contains an invalid tool")
    if input_schema is None:
        raise McpProtocolError("tools/list contains an invalid input schema")

    return McpToolDescription(
        name=name,
        title=title,
        description=description,
        input_schema=MappingProxyType(dict(input_schema)),
    )


def _as_object(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    if not all(isinstance(key, str) for key in value):
        return None
    return value


def _tool_definition_from(
    *,
    server_name: str,
    description: McpToolDescription,
) -> ToolDefinition:
    display_name = description.title if description.title else description.name
    schema_hash = _schema_hash(description.input_schema)

    return ToolDefinition(
        tool_id=f"mcp:{server_name}:{description.name}:{schema_hash}",
        display_name=display_name,
        description=description.description,
        input_schema=description.input_schema,
        risk_level="medium",
        required_permissions=frozenset({"mcp.execute"}),
        requires_approval=True,
        timeout_seconds=_MCP_TOOL_TIMEOUT_SECONDS,
    )


def _schema_hash(input_schema: Mapping[str, object]) -> str:
    canonical = json.dumps(
        dict(input_schema),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
