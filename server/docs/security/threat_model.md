# Threat Model

## System Overview

The backend is a secure relay for direct 1:1 encrypted messaging. It authenticates users, stores public device key material, stores public one-time prekeys, stores opaque encrypted `wire_payload_json`, enforces access control, rotates refresh tokens, records audit events, and applies basic rate limits.

The backend does not decrypt messages, does not call Signal crypto, does not store private keys, does not store plaintext message content, and does not support group chats or conversations.

## Assets

- User accounts
- Argon2id password hashes
- Refresh session hashes
- JWT access-token signing secret in deployment configuration
- Refresh-token HMAC secret in deployment configuration
- Public device key material
- Public one-time prekeys
- Opaque encrypted message payloads
- Audit logs
- PostgreSQL database records

## Actors

- Anonymous attacker
- Authenticated user
- Malicious sender
- Malicious recipient
- Compromised token holder
- Database attacker
- Developer/operator with deployment access

## Trust Boundaries

- Client to FastAPI API
- FastAPI application to PostgreSQL
- Backend configuration to runtime secrets
- Authenticated user identity from verified JWT to object-level authorization checks
- Client crypto package to backend relay storage

## Attack Surfaces

- Authentication and refresh-token endpoints
- Current-user dependency and Bearer token parsing
- Public key and one-time prekey relay endpoints
- Direct message send/fetch/list/forward/revoke/delete endpoints
- Pydantic request validation
- Audit logging
- Rate limiting and security headers
- PostgreSQL persistence layer

## STRIDE-Style Risks And Mitigations

| Risk | Example | Mitigation |
| --- | --- | --- |
| Spoofing | Forged JWT or sender ID spoofing | JWT signature/expiry/type validation; sender identity from `current_user.id` only |
| Tampering | Message access revoked by non-sender | Service-layer object-level checks; safe 404 for inaccessible resources |
| Repudiation | User denies security-relevant action | Audit logs for auth, key relay, message access, revoke, delete, and denial events |
| Information disclosure | Password hashes, tokens, plaintext, private keys, or wire payloads leak | Response schemas, audit sanitization, no plaintext/private key storage |
| Denial of service | Brute-force login or message spam | In-memory rate limits and request validation |
| Elevation of privilege | Accessing another user's messages | Direct sender/recipient checks and current-user dependency |

## Specific Threats

- Brute-force login
- Token theft and refresh-token replay
- Broken object-level access control
- SQL injection-style input
- Malformed encrypted relay payloads
- One-time prekey scraping or overuse
- Audit log leakage
- Database compromise
- Denial-of-service or API abuse

## Implemented Mitigations

- Argon2id password hashing
- Generic authentication failures
- JWT access-token validation
- Refresh-token rotation and HMAC-hashed refresh-token storage
- Current-user dependency for protected routes
- Direct message access-control checks
- Revoke and delete visibility fields
- Pydantic validation with `extra="forbid"` for sensitive request shapes
- Async SQLAlchemy ORM queries instead of string-built SQL
- Audit log sanitization
- Rate limiting
- Security headers
- CORS configuration hardening

## Limitations

- In-memory rate limiting is not distributed.
- No MFA.
- No Redis-backed session/rate-limit store.
- No production WAF/API gateway.
- No admin audit-log viewer.
- Secret management depends on deployment configuration.
- OWASP ZAP/dependency scanning is optional/manual unless added later.
