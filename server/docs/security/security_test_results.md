# Security Test Results

Date documented: 2026-06-02

## Automated Test Commands

```bash
ruff check app tests alembic
python -m compileall app tests alembic
pytest tests/security -vv
pytest tests/unit tests/integration tests/security -q
```

## Current Result Summary

The security evidence pack adds pytest tests for authentication, access control, input validation, injection resistance, sensitive data exposure, audit logging, and rate limiting.

Verification performed in this workspace on 2026-06-02:

- `ruff check app tests alembic`: passed
- `python -m compileall app tests alembic`: passed
- `pytest tests/security -q`: 2 passed, 54 skipped
- `pytest tests/unit tests/integration tests/security -q`: 52 passed, 255 skipped

The skipped tests are the database-backed integration/security tests. The test fixture requires `TEST_DATABASE_URL` to be configured, to be different from `DATABASE_URL`, and to point at a database name containing `test`. Run the same commands on the VM or local environment with a migrated PostgreSQL test database before final submission, then replace the skipped counts with the full pass counts.

| Area | Evidence | Expected Result |
| --- | --- | --- |
| Authentication | `tests/security/test_auth_security.py` | Generic failures, invalid tokens rejected, refresh rotation enforced |
| Access control | `tests/security/test_access_control_security.py` | Users only access direct messages they send or receive |
| Input validation | `tests/security/test_input_validation_security.py` | Malformed payloads and unexpected fields rejected |
| Injection resistance | `tests/security/test_input_validation_security.py` | Injection-style inputs do not bypass auth or leak DB errors |
| Sensitive data exposure | `tests/security/test_sensitive_data_security.py` | Responses and audit logs avoid secrets and plaintext |
| Rate limiting | `tests/security/test_rate_limit_security.py` | Repeated abuse returns `429` with safe errors |
| TLS utility | `tests/unit/test_tls_connection_probe.py` | Host resolution/certificate-name formatting utility behavior covered |
| Security headers | `tests/integration/test_security_headers.py` | Core hardening headers present and wildcard production CORS rejected |

## Key Controls Verified

- Argon2id password hashes are not exposed by API responses.
- Login failures use generic responses.
- JWT access tokens are validated for signature, expiry, type, and subject.
- Refresh-token rotation prevents reuse of old refresh tokens.
- Direct message object-level access checks prevent unrelated access.
- Revocation and per-user delete visibility are enforced.
- Public message APIs reject plaintext-like fields and unsupported conversation/group fields.
- LibSignal-style `wire_payload_json` requires `format=libsignal-v1`, allowed type values, base64 `bodyB64`, and rejects forbidden plaintext/private/session-state keys.
- User lookup hides email, public key material, password hashes, and refresh-token hashes.
- Audit logs record security events without storing passwords, tokens, key material, or encrypted wire payloads.
- Rate limiting mitigates brute-force login, registration spam, refresh abuse, and message spam at a basic local-project level.

## Evidence Placeholders

- Pytest security test output in this workspace: `2 passed, 54 skipped`
- Full unit/integration/security suite output in this workspace: `52 passed, 255 skipped`
- Full DB-backed security test output: pending rerun with `TEST_DATABASE_URL`
- Full DB-backed suite output: pending rerun with `TEST_DATABASE_URL`
- Optional curl/httpie manual check: not recorded yet
- Optional OWASP ZAP baseline summary: not recorded yet
- Optional `pip-audit` output: not recorded yet
- Optional public TLS probe output: not recorded yet

## Residual Risks

- The in-memory rate limiter is not distributed and is suitable only for local/single-instance deployment.
- JWT and refresh-token hash secrets depend on deployment environment management.
- Multi-factor authentication is not implemented.
- Redis-backed session/rate-limit storage is not implemented.
- No production WAF is configured by this backend.
- No admin audit-log viewer is exposed.
- Automated dependency vulnerability scanning is not included yet.
- FastAPI does not currently enforce HTTPS/HSTS in application code; TLS policy depends on gateway/Nginx configuration.
