import asyncio
import json
import os
import socket
from dataclasses import dataclass
from typing import Final

import uvicorn
from fastapi import FastAPI

_LOCAL_HOST: Final = "127.0.0.1"
_PROTOCOL_VERSION: Final = 1
READY_PREFIX: Final = "ASAGENT_READY "
_STARTUP_TIMEOUT_SECONDS: Final = 5.0


@dataclass(frozen=True, slots=True)
class ServerReady:
    host: str
    port: int
    pid: int
    protocol_version: int = _PROTOCOL_VERSION

    def to_json(self) -> str:
        return json.dumps(
            {
                "host": self.host,
                "pid": self.pid,
                "port": self.port,
                "protocol_version": self.protocol_version,
            },
            separators=(",", ":"),
            sort_keys=True,
        )


class LocalApiServer:
    """Owns one localhost-only Uvicorn server lifecycle."""

    def __init__(
        self,
        app: FastAPI,
        *,
        host: str = _LOCAL_HOST,
        port: int = 0,
    ) -> None:
        if host != _LOCAL_HOST:
            raise ValueError("local API host must be 127.0.0.1")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError("local API port must be an integer")
        if not 0 <= port <= 65535:
            raise ValueError("local API port must be between 0 and 65535")

        self._app = app
        self._host = host
        self._port = port
        self._listener: socket.socket | None = None
        self._server: uvicorn.Server | None = None
        self._serve_task: asyncio.Task[None] | None = None

    async def start(self) -> ServerReady:
        if self._serve_task is not None:
            raise RuntimeError("local API server has already been started")

        listener = self._bind_listener()
        server = uvicorn.Server(
            uvicorn.Config(
                self._app,
                host=self._host,
                port=self._port,
                access_log=False,
                lifespan="off",
                log_config=None,
            ),
        )

        self._listener = listener
        self._server = server
        self._serve_task = asyncio.create_task(
            server.serve(sockets=[listener]),
            name="asagent-local-api",
        )

        try:
            async with asyncio.timeout(_STARTUP_TIMEOUT_SECONDS):
                await self._wait_until_started()
        except BaseException:
            await self.close()
            raise

        return ServerReady(
            host=self._host,
            port=listener.getsockname()[1],
            pid=os.getpid(),
        )

    async def wait_closed(self) -> None:
        if self._serve_task is None:
            raise RuntimeError("local API server has not been started")

        try:
            await self._serve_task
        finally:
            self._close_listener()

    async def close(self) -> None:
        if self._server is not None:
            self._server.should_exit = True

        if self._serve_task is not None:
            await self.wait_closed()

    def _bind_listener(self) -> socket.socket:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            listener.bind((self._host, self._port))
        except OSError:
            listener.close()
            raise

        return listener

    async def _wait_until_started(self) -> None:
        if self._server is None or self._serve_task is None:
            raise RuntimeError("local API server has not been configured")

        while not self._server.started:
            if self._serve_task.done():
                await self._serve_task
                raise RuntimeError("local API server stopped before startup")

            await asyncio.sleep(0)

    def _close_listener(self) -> None:
        if self._listener is not None:
            self._listener.close()
