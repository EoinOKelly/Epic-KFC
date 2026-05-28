# Penetration Testing Plan

## Scope

This plan covers the FastAPI backend for the secure messaging project. The backend supports authenticated direct 1:1 encrypted message relay, public device key relay, one-time prekey relay, refresh-token rotation, audit logging, rate limiting, security headers, and CORS hardening.

## Out Of Scope

- Frontend testing
- Blockchain transaction submission
- Smart contract testing
- Message encryption or decryption
- Signal library internals
- Group chats
- Conversation routes
- Real user credentials or production data

## Test Environment

- Local FastAPI app exercised through pytest and httpx ASGI transport
- Guarded PostgreSQL test database from `TEST_DATABASE_URL`
- Fake test users, fake devices, fake prekeys, and fake opaque encrypted payloads
- Test JWT and refresh-token secrets monkeypatched for repeatability
- In-memory rate limiter reset between tests

## Target Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `PUT /api/v1/keys/devices/{device_id}`
- `POST /api/v1/keys/devices/{device_id}/one-time-prekeys`
- `GET /api/v1/keys/users/{user_id}/devices/{device_id}/prekey-bundle`
- `POST /api/v1/messages`
- `GET /api/v1/messages/received`
- `GET /api/v1/messages/sent`
- `GET /api/v1/messages/{message_id}`
- `POST /api/v1/messages/{message_id}/forward`
- `POST /api/v1/messages/{message_id}/revoke`
- `DELETE /api/v1/messages/{message_id}`

## Tools

- pytest security tests under `tests/security`
- httpx ASGI transport for repeatable endpoint testing
- curl or httpie for optional manual endpoint checks
- Postman or Insomnia collections if manual demonstrations are needed
- OWASP ZAP baseline scan as an optional manual check against a local running API
- Manual review for sensitive data exposure in responses and audit logs

## Test Categories

- Authentication attacks
- Broken object-level access control
- Input validation failures
- Injection-style payloads
- Sensitive data exposure
- Rate limiting and API abuse
- Audit logging evidence

## Expected Results

- Authentication failures return generic safe errors.
- Invalid, expired, wrong-signature, and wrong-type tokens are rejected.
- Users cannot access, revoke, delete, or list messages outside their direct sender/recipient role.
- Direct message routes reject unsupported group/conversation fields.
- Malformed encrypted payloads and malformed public key fields are rejected.
- Injection-style payloads do not bypass authentication and do not expose database errors.
- Responses and audit logs do not expose passwords, hashes, tokens, private keys, plaintext, or wire payloads.
- Repeated abusive requests return `429 Too Many Requests` with `Retry-After`.

## Safety Notes

- Use fake test data only.
- Do not run these tests against production.
- Do not store real credentials, tokens, key material, or message payloads in documentation.
- Do not print secrets in test output.
- Keep OWASP ZAP/manual scans limited to the local development environment unless explicitly authorized.
