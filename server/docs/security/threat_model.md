# Threat Model

## System Overview

The backend is an authenticated relay for direct 1:1 encrypted messaging. It stores account records, refresh-session hashes, public device keys, public one-time prekeys, opaque encrypted `wire_payload_json`, message visibility metadata, and audit events.

The backend does not decrypt messages, call Signal cryptography, store private keys, store plaintext message content, store ratchet/session state, support group chats, or submit blockchain transactions.

## Assets

- User accounts
- Argon2id password hashes
- Refresh session HMAC hashes
- JWT signing secret in deployment configuration
- Refresh-token HMAC secret in deployment configuration
- JWT access tokens held by clients
- Raw refresh tokens held by clients
- Public device key material
- Public one-time prekeys
- Opaque encrypted relay payloads
- Message metadata and visibility timestamps
- Audit logs
- PostgreSQL database records
- VM deployment configuration

## Attackers

- Anonymous attacker
- Passive network attacker
- Active network attacker
- Authenticated malicious user
- Malicious sender
- Malicious recipient
- Compromised token holder
- Database attacker
- Honest-but-curious server/operator
- Compromised server
- Fully compromised client device

## Trust Boundaries

- Client device to public TLS gateway
- Gateway to VM/Nginx internal HTTP
- Nginx to FastAPI localhost
- FastAPI to PostgreSQL
- Environment configuration to runtime secrets
- Verified JWT subject to object-level authorization checks
- Client cryptography package to backend relay storage
- Backend audit/event data to operator review

## Attack Surfaces

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- User discovery route
- Public device key upload route
- One-time prekey upload route
- Prekey bundle fetch route
- Message send/list/fetch/forward/revoke/delete routes
- Pydantic validation and error reporting
- JWT Bearer parsing
- Refresh-token rotation database state
- Audit logging
- Rate limiting
- CORS/security header configuration
- PostgreSQL persistence
- Nginx/gateway deployment

## STRIDE-Style Risks And Mitigations

| Risk | Example | Mitigation |
| --- | --- | --- |
| Spoofing | Forged JWT or sender ID spoofing | JWT signature, expiry, required claim, and token type validation; sender identity comes from `current_user.id` only |
| Tampering | Non-sender revokes a message | Service-layer sender/recipient checks and safe 404 responses for inaccessible objects |
| Repudiation | User denies auth/key/message action | Audit logs for auth success/failure, key relay events, message success events, and denied message operations |
| Information disclosure | Password hashes, tokens, plaintext, private keys, or audit secrets leak | Response schemas, validation sanitization, audit detail allowlist, no plaintext/private key storage |
| Denial of service | Brute-force login or message spam | In-memory fixed-window rate limits and strict request size limits |
| Elevation of privilege | User fetches another user's message | Current-user dependency and repository visibility predicates |

## Specific Threats

### Passive Network Attacker

Threat: observes traffic between public clients and the service.

Mitigation: public users connect to `https://kfc.theburkenator.com`; TLS is terminated by the provided gateway using a public certificate. The backend stores encrypted message payloads rather than plaintext.

Residual risk: gateway-to-VM traffic is internal HTTP after TLS termination.

### Active Network Attacker

Threat: modifies traffic, redirects clients, or attempts downgrade/MITM attacks.

Mitigation: clients should validate the public certificate and hostname. Nginx/gateway should be configured to preserve the intended host and forward only to the internal FastAPI port. JWT signatures prevent modified Bearer tokens from authenticating.

Residual risk: FastAPI code does not currently enforce HTTPS or HSTS itself; that must be handled by the gateway/Nginx layer.

### Broken Authentication

Threat: credential stuffing, account enumeration, invalid JWTs, refresh-token replay.

Mitigation: Argon2id password hashes, generic auth errors, inactive-user rejection, short-lived JWTs, HS256 algorithm pinning, required JWT claims, HMAC refresh-token hashes, refresh-token rotation, logout revocation, and login/register/refresh rate limits.

### Broken Access Control

Threat: authenticated user accesses, revokes, deletes, forwards, or lists messages belonging to another user.

Mitigation: protected routes use `get_current_user`; message service checks sender/recipient relationship; list queries are scoped by current user; sender-only revoke; per-user delete visibility.

### Injection

Threat: SQL injection through login, username, UUID, or message inputs.

Mitigation: strict request validation and SQLAlchemy ORM expressions instead of string-built SQL.

### Sensitive Data Exposure

Threat: API responses or audit logs expose passwords, password hashes, refresh-token hashes, raw tokens, private keys, plaintext, or wire payloads.

Mitigation: response schemas omit password/session hashes; user discovery hides email/key material; audit details are allowlisted; validation errors are sanitized. Message responses intentionally include opaque encrypted `wire_payload_json` only for authorized users.

### Honest-But-Curious Server

Threat: backend/operator can inspect database contents.

Mitigation: backend stores encrypted message payloads and public key material only. It does not store plaintext messages or private keys.

Residual risk: metadata such as sender, recipient, device IDs, timestamps, and message visibility state is visible to the server.

### Compromised Server

Threat: attacker controls the backend or database.

Mitigation: message confidentiality still depends on client-side encryption and no private key storage. Passwords are Argon2id hashes and refresh tokens are HMAC hashes rather than raw tokens.

Residual risk: a compromised server can modify key material, deny service, issue malicious responses, inspect metadata, steal environment secrets, and capture future tokens sent to it.

### Fully Compromised Client Device

Threat: attacker controls a user's endpoint.

Mitigation: backend can revoke refresh sessions only when tokens are submitted or all sessions are revoked through service code. The backend cannot protect private keys stored on a compromised client.

Residual risk: compromised clients can read plaintext before encryption/after decryption and can act as the user while holding valid tokens.

## Implemented Mitigations

- Argon2id password hashing.
- Generic authentication failures.
- JWT access-token validation.
- Refresh-token rotation and HMAC-hashed refresh-token storage.
- Current-user dependency for protected routes.
- Direct message object-level access-control checks.
- Revoke and delete visibility fields.
- Strict Pydantic validation with `extra="forbid"`.
- LibSignal wire payload structural validation.
- Base64 validation for public key material.
- Async SQLAlchemy ORM queries instead of string-built SQL.
- Audit log sanitization.
- Rate limiting.
- Basic security headers.
- CORS configuration hardening.
- `.env` ignored and `.env.example` committed.

## Residual Risks

- In-memory rate limiting is not distributed.
- No MFA.
- No Redis-backed session/rate-limit store.
- PostgreSQL and backend run on the same VM for the prototype.
- Public TLS terminates at the gateway, not inside FastAPI.
- FastAPI does not currently set HSTS or enforce HTTPS.
- Backend cannot prove ciphertext cryptographically used a claimed prekey.
- Backend does not protect against a fully compromised client device.
- No admin audit-log viewer.
- Secret management depends on deployment environment handling.
- Dependency scan evidence must be refreshed before final submission.
