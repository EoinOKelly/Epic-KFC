"""Application entry point for the secure messaging API."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .api.v1.router import api_router
from .core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title=settings.app_name)
    _configure_cors(app)
    _configure_security_headers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


def _configure_cors(app: FastAPI) -> None:
    """Configure CORS with explicit allowed origins only."""
    if not settings.allowed_origins:
        return

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _configure_security_headers(app: FastAPI) -> None:
    """Add basic hardening headers to API responses."""

    @app.middleware("http")
    async def security_headers_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if settings.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
        return response


app = create_app()
