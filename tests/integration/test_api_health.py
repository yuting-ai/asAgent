import httpx
import pytest

from asagent.api.app import create_app
from asagent.api.auth import LocalApiToken

_TOKEN = LocalApiToken("test-token")


@pytest.mark.asyncio
async def test_health_endpoint_accepts_the_current_local_api_token() -> None:
    app = create_app(access_token=_TOKEN)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    (
        {},
        {"Authorization": "Basic test-token"},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "Bearer test token"},
    ),
)
async def test_health_endpoint_rejects_invalid_local_api_credentials(
    headers: dict[str, str],
) -> None:
    app = create_app(access_token=_TOKEN)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid local API credentials"}
    assert response.headers["www-authenticate"] == "Bearer"
