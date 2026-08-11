import json
import os

import httpx
import pytest

from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken
from asagent.api.server import LocalApiServer
from asagent.storage.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)

_TOKEN = LocalApiToken("test-token")


@pytest.mark.asyncio
async def test_local_api_server_binds_loopback_dynamic_port_and_serves_health() -> None:
    server = LocalApiServer(
        create_app(
            access_token=_TOKEN,
            conversations=InMemoryConversationRepository(),
        ),
        port=0,
    )
    ready = await server.start()

    try:
        assert ready.host == "127.0.0.1"
        assert ready.port > 0
        assert ready.pid == os.getpid()
        assert json.loads(ready.to_json()) == {
            "host": "127.0.0.1",
            "pid": os.getpid(),
            "port": ready.port,
            "protocol_version": 1,
        }

        async with httpx.AsyncClient(
            base_url=f"http://{ready.host}:{ready.port}",
        ) as client:
            response = await client.get(
                "/api/v1/health",
                headers={"Authorization": "Bearer test-token"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        await server.close()


@pytest.mark.parametrize(
    ("host", "port", "message"),
    [
        ("0.0.0.0", 0, "host must be 127.0.0.1"),
        ("127.0.0.1", -1, "port must be between 0 and 65535"),
        ("127.0.0.1", 65536, "port must be between 0 and 65535"),
        ("127.0.0.1", True, "port must be an integer"),
    ],
)
def test_local_api_server_rejects_unsafe_or_invalid_binding(
    host: str,
    port: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        LocalApiServer(
            create_app(
                access_token=_TOKEN,
                conversations=InMemoryConversationRepository(),
            ),
            host=host,
            port=port,
        )
