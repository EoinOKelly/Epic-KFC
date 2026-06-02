"""Integration tests for security headers and CORS hardening."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, settings as app_settings
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


async def test_https_response_includes_hsts_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTPS responses include HSTS when transport hardening is enabled."""
    monkeypatch.setattr(app_settings, "security_headers_enabled", True)
    monkeypatch.setattr(app_settings, "hsts_enabled", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


async def test_https_enforcement_rejects_plain_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API can reject non-TLS requests when deployed in enforce mode."""
    monkeypatch.setattr(app_settings, "enforce_https", True)
    monkeypatch.setattr(app_settings, "trust_x_forwarded_proto", False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 426
    assert response.json()["detail"] == "HTTPS is required"


async def test_https_enforcement_trusts_configured_proxy_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A TLS-terminating reverse proxy can signal HTTPS to the app."""
    monkeypatch.setattr(app_settings, "enforce_https", True)
    monkeypatch.setattr(app_settings, "trust_x_forwarded_proto", True)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"x-forwarded-proto": "https"},
    ) as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert "Strict-Transport-Security" in response.headers


async def test_production_wildcard_cors_is_rejected() -> None:
    """Production settings must not allow wildcard CORS origins."""
    with pytest.raises(ValueError, match="ALLOWED_ORIGINS"):
        Settings(app_env="production", allowed_origins=["*"])


async def test_cors_credentials_reject_wildcard_origin() -> None:
    """Credentialed CORS must not be combined with wildcard origins."""
    with pytest.raises(ValueError, match="CORS_ALLOW_CREDENTIALS"):
        Settings(allowed_origins=["*"], cors_allow_credentials=True)


async def test_production_rejects_placeholder_secrets() -> None:
    """Production settings must not run with sample shared secrets."""
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            app_env="production",
            allowed_origins=["https://example.com"],
            jwt_secret_key="change_me_local_dev_only",
            refresh_token_hash_secret="change_me_refresh_hash_secret_local_only",
        )
