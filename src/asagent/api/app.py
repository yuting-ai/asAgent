from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app() -> FastAPI:
    app = FastAPI(
        title="asAgent Local API",
        version="0.1.0",
    )

    @app.get(
        "/api/v1/health",
        response_model=HealthResponse,
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    return app
