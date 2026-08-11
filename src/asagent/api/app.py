from typing import Literal

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from asagent.api.auth import BearerTokenAuthenticator, LocalApiToken


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(*, access_token: LocalApiToken) -> FastAPI:
    app = FastAPI(
        title="asAgent Local API",
        version="0.1.0",
    )
    authenticate = BearerTokenAuthenticator(access_token)

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
        dependencies=[Depends(authenticate)],
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    return app
