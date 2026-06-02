"""Resolve a host name and verify a TLS connection.

This small operator utility is intentionally low-level: it uses ``socket`` for
DNS/address resolution and TCP, then wraps the socket with Python's OpenSSL
bindings through ``ssl``. It is useful as submission evidence that the backend
team can resolve host names and establish certificate-verified TLS sessions.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
from dataclasses import asdict, dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ResolvedAddress:
    """A single stream socket address returned by DNS resolution."""

    family: int
    socket_type: int
    proto: int
    socket_address: tuple[Any, ...]

    @property
    def display_address(self) -> str:
        """Return a stable address string for JSON output."""
        return str(self.socket_address[0])


@dataclass(frozen=True)
class TLSConnectionResult:
    """Non-secret TLS connection details suitable for documentation."""

    host: str
    port: int
    server_hostname: str
    peer_address: str
    tls_version: str
    cipher: str
    certificate_subject: str
    certificate_issuer: str
    certificate_not_after: str | None
    resolved_addresses: list[str]


def resolve_host(host: str, port: int) -> list[ResolvedAddress]:
    """Resolve a host name to stream socket addresses."""
    address_info = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    resolved: list[ResolvedAddress] = []
    seen: set[tuple[int, tuple[Any, ...]]] = set()

    for family, socket_type, proto, _, socket_address in address_info:
        dedupe_key = (family, socket_address)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        resolved.append(
            ResolvedAddress(
                family=family,
                socket_type=socket_type,
                proto=proto,
                socket_address=socket_address,
            )
        )

    if not resolved:
        raise RuntimeError(f"No stream socket addresses resolved for {host}:{port}.")

    return resolved


def check_tls_connection(
    host: str,
    port: int = 443,
    *,
    server_hostname: str | None = None,
    timeout_seconds: float = 5.0,
    cafile: str | None = None,
) -> TLSConnectionResult:
    """Resolve ``host``, connect, and verify the server certificate."""
    verified_hostname = server_hostname or host
    resolved_addresses = resolve_host(host, port)
    context = ssl.create_default_context(cafile=cafile)
    context.check_hostname = True
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.verify_mode = ssl.CERT_REQUIRED
    last_error: OSError | None = None

    for resolved in resolved_addresses:
        raw_socket: socket.socket | None = socket.socket(
            resolved.family,
            resolved.socket_type,
            resolved.proto,
        )
        raw_socket.settimeout(timeout_seconds)
        try:
            raw_socket.connect(resolved.socket_address)
            tls_socket = context.wrap_socket(
                raw_socket,
                server_hostname=verified_hostname,
            )
            raw_socket = None
            with tls_socket:
                certificate = tls_socket.getpeercert()
                cipher_info = tls_socket.cipher()
                return TLSConnectionResult(
                    host=host,
                    port=port,
                    server_hostname=verified_hostname,
                    peer_address=resolved.display_address,
                    tls_version=tls_socket.version() or "unknown",
                    cipher=cipher_info[0] if cipher_info else "unknown",
                    certificate_subject=_format_certificate_name(
                        certificate.get("subject", ())
                    ),
                    certificate_issuer=_format_certificate_name(
                        certificate.get("issuer", ())
                    ),
                    certificate_not_after=certificate.get("notAfter"),
                    resolved_addresses=[
                        address.display_address for address in resolved_addresses
                    ],
                )
        except OSError as exc:
            last_error = exc
        finally:
            if raw_socket is not None:
                raw_socket.close()

    raise RuntimeError(
        f"Could not establish verified TLS to {host}:{port}: {last_error}"
    )


def _format_certificate_name(name: Sequence[Sequence[tuple[str, str]]]) -> str:
    """Format a certificate subject or issuer tuple from ``getpeercert``."""
    parts: list[str] = []
    for relative_distinguished_name in name:
        for key, value in relative_distinguished_name:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the TLS probe from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Host name to resolve and connect to")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument(
        "--server-hostname",
        help="SNI and certificate hostname to verify; defaults to host",
    )
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--cafile", help="Optional CA bundle path")
    args = parser.parse_args(argv)

    result = check_tls_connection(
        args.host,
        args.port,
        server_hostname=args.server_hostname,
        timeout_seconds=args.timeout,
        cafile=args.cafile,
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
