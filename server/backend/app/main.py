"""Application entry point for the secure messaging API."""

from fastapi import FastAPI

from .api.v1.router import api_router
from .core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
