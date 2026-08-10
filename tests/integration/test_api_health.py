import httpx
import pytest

from asagent.api.app import create_app


@pytest.mark.asyncio
async def test_health_endpoint_returns_liveness_status() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
