"""Integration tests for security headers and CORS hardening."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app


pytestmark = pytest.mark.asyncio


async def test_normal_api_response_includes_security_headers() -> None:
    """API responses include basic browser hardening headers."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


async def test_cache_control_no_store_is_present() -> None:
    """API responses should not be cached by default."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.headers["Cache-Control"] == "no-store"


async def test_production_wildcard_cors_is_rejected() -> None:
    """Production settings must not allow wildcard CORS origins."""
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        Settings(app_env="production", allowed_origins=["*"])
