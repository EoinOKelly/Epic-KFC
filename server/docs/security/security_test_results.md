# Security Test Results

Date documented: 2026-06-02

## Automated Test Commands

```bash
.venv/bin/ruff check app tests alembic scripts
.venv/bin/python -m compileall app tests scripts alembic
.venv/bin/bandit -q -r app scripts
.venv/bin/pip-audit --progress-spinner off --cache-dir /private/tmp/pip-audit-cache
.venv/bin/pip-audit --progress-spinner off --cache-dir /private/tmp/pip-audit-cache -r requirements.txt
.venv/bin/pytest tests/security -vv
.venv/bin/pytest tests/unit tests/integration/test_security_headers.py -q
.venv/bin/pytest tests/unit tests/integration tests/security -q
```

## Current Result Summary

The security evidence pack adds pytest tests for authentication, access control, input validation, injection resistance, sensitive data exposure, audit logging, transport hardening, TLS evidence helpers, and rate limiting.

Verification recorded in this workspace on 2026-06-02:

- `.venv/bin/ruff check app tests alembic scripts`: passed
- `.venv/bin/python -m compileall app tests scripts alembic`: passed
- `.venv/bin/bandit -q -r app scripts`: passed
- `.venv/bin/pip-audit --progress-spinner off --cache-dir /private/tmp/pip-audit-cache`: no known vulnerabilities found
- `.venv/bin/pip-audit --progress-spinner off --cache-dir /private/tmp/pip-audit-cache -r requirements.txt`: no known vulnerabilities found
- `.venv/bin/pytest tests/unit tests/integration/test_security_headers.py -q`: 56 passed
- `.venv/bin/pytest tests/unit tests/integration tests/security -q`: interrupted locally after 48 passed, 2 skipped because the unavailable PostgreSQL test database caused repeated connection timeouts
- `pytest tests/unit -q`: 48 passed after the blockchain-anchor implementation
- `alembic history`: passed
- `alembic upgrade head --sql`: rendered successfully
- `alembic current`: blocked locally because PostgreSQL was not listening on `localhost:5432`
- `pytest tests/integration/test_blockchain_routes.py -vv -rs`: skipped locally because the guarded PostgreSQL test database was unavailable


Database-backed integration/security tests require `TEST_DATABASE_URL` to be configured, to be different from `DATABASE_URL`, and to point at a database name containing `test`. Run the same commands on the VM or local environment with a migrated PostgreSQL test database before final submission, then replace the skipped or blocked counts with full pass counts.

| Area | Evidence | Expected Result |
| --- | --- | --- |
| Authentication | `tests/security/test_auth_security.py` | Generic failures, invalid tokens rejected, refresh rotation enforced |
| Access control | `tests/security/test_access_control_security.py` | Users only access direct messages they send or receive |
| Input validation | `tests/security/test_input_validation_security.py` | Malformed payloads and unexpected fields rejected |
| Injection resistance | `tests/security/test_input_validation_security.py` | Injection-style inputs do not bypass auth or leak DB errors |
| Sensitive data exposure | `tests/security/test_sensitive_data_security.py` | Responses and audit logs avoid secrets and plaintext |
| Rate limiting | `tests/security/test_rate_limit_security.py` | Repeated abuse returns `429` with safe errors |
| Blockchain anchors | `tests/integration/test_blockchain_routes.py` | Pending anchors are created/reused, anchor status is protected by message access, verification checks metadata |
| TLS utility | `tests/unit/test_tls_connection_probe.py` | Host resolution/certificate-name formatting utility behavior covered |
| Security headers / HTTPS | `tests/integration/test_security_headers.py` | Core hardening headers present, HSTS emitted for HTTPS, optional HTTPS enforcement works, wildcard production CORS rejected |
| Vulnerable components | `pip-audit` and `pip-audit -r requirements.txt` | No known vulnerabilities in the backend virtualenv or declared requirements |

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
- HTTPS enforcement can reject plain HTTP, HSTS is emitted on HTTPS responses, and production settings reject placeholder JWT/refresh-token secrets.
- Bandit produced no findings after suppressing known false positives for non-secret OAuth/hash-prefix literals.
- The backend virtualenv and declared requirements currently have no known vulnerabilities according to `pip-audit`.
- Message send and forward now create pending blockchain anchors automatically.
- Blockchain verification currently checks backend metadata, not live Sepolia state.

## Residual Risks

- The in-memory rate limiter is not distributed and is suitable only for local/single-instance deployment.
- JWT and refresh-token hash secrets depend on deployment environment management.
- Multi-factor authentication is not implemented.
- Redis-backed session/rate-limit storage is not implemented.
- No production WAF is configured by this backend.
- No admin audit-log viewer is exposed.
- Dependency scan evidence should be refreshed immediately before submission.
- FastAPI HTTPS/HSTS enforcement is implemented but depends on production env flags being enabled behind the gateway/Nginx configuration.
- Blockchain anchors remain pending until a separate worker submits them to Sepolia and updates confirmation metadata.
