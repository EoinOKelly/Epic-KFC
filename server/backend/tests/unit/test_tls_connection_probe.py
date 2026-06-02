"""Unit tests for the TLS connection probe utility."""

from __future__ import annotations

import socket

import pytest

from scripts.check_tls_connection import _format_certificate_name, resolve_host


def test_resolve_host_deduplicates_stream_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Host resolution should return unique stream socket addresses."""

    def fake_getaddrinfo(host: str, port: int, **kwargs):
        assert host == "api.example.test"
        assert port == 443
        assert kwargs["type"] == socket.SOCK_STREAM
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("203.0.113.10", 443),
            ),
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("203.0.113.10", 443),
            ),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    resolved = resolve_host("api.example.test", 443)

    assert [address.display_address for address in resolved] == ["203.0.113.10"]


def test_resolve_host_rejects_empty_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host with no stream addresses should fail clearly."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [])

    with pytest.raises(RuntimeError, match="No stream socket addresses"):
        resolve_host("api.example.test", 443)


def test_format_certificate_name() -> None:
    """Certificate names are flattened for readable evidence output."""
    certificate_name = (
        (("countryName", "IE"),),
        (("organizationName", "Example API"),),
        (("commonName", "api.example.test"),),
    )

    assert _format_certificate_name(certificate_name) == (
        "countryName=IE, organizationName=Example API, commonName=api.example.test"
    )
