"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from grm.api.routes import health, turns
from grm.observability.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="GRM", version="0.1.0")
    app.include_router(health.router)
    app.include_router(turns.router)
    return app


app = create_app()
