"""Application entry point for the secure messaging API."""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .api.v1.router import api_router
from .core.config import settings


SENSITIVE_VALIDATION_FIELDS = {
    "access_token",
    "body",
    "content",
    "password",
    "password_hash",
    "plaintext",
    "private_key",
    "refresh_token",
    "refresh_token_hash",
    "wire_payload_json",
}


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title=settings.app_name)
    _configure_cors(app)
    _configure_security_headers(app)
    _configure_validation_error_handler(app)
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


def _configure_validation_error_handler(app: FastAPI) -> None:
    """Return validation errors without echoing submitted secret values."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        _ = request
        return JSONResponse(
            status_code=422,
            content={"detail": [_sanitize_validation_error(error) for error in exc.errors()]},
        )


def _sanitize_validation_error(error: dict[str, Any]) -> dict[str, Any]:
    """Remove submitted inputs and redact sensitive field names from errors."""
    sanitized: dict[str, Any] = {
        "type": error.get("type"),
        "loc": [
            "[redacted]" if str(part) in SENSITIVE_VALIDATION_FIELDS else part
            for part in error.get("loc", [])
        ],
        "msg": error.get("msg"),
    }
    return {key: value for key, value in sanitized.items() if value is not None}


app = create_app()
