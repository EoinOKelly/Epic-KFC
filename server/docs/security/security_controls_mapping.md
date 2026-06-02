# Security Controls Mapping

This document maps the backend implementation to the cybersecurity brief areas and the evidence available in code and tests.

| Rubric issue | Backend control | Evidence |
| --- | --- | --- |
| Secure authentication | Argon2id password hashing, generic login failures, active-user checks | `backend/app/services/password_service.py`, `backend/app/services/auth_service.py`, `backend/tests/security/test_auth_security.py` |
| Broken authentication | JWT signature/expiry/type/subject validation, refresh-token rotation, logout revocation | `backend/app/services/token_service.py`, `backend/app/api/deps.py`, `backend/tests/unit/test_token_service.py`, `backend/tests/integration/test_current_user.py` |
| Broken access control | `get_current_user`, route dependencies, sender/recipient message checks, sender-only revoke, per-user delete visibility | `backend/app/services/message_service.py`, `backend/app/repositories/message_repository.py`, `backend/tests/security/test_access_control_security.py` |
| Improper input validation | Pydantic schemas with `extra="forbid"`, username/email/password constraints, UUID/path validation, base64 validation, strict wire payload validation | `backend/app/schemas/*.py`, `backend/tests/security/test_input_validation_security.py`, `backend/tests/unit/test_wire_payload_validation.py` |
| Injection | SQLAlchemy 2.x ORM expressions, no repository `Session.query`, no obvious f-string SQL execution, injection-style login/username tests | `backend/app/repositories/*.py`, `backend/tests/security/test_input_validation_security.py` |
| Cryptographic issues | Passwords use Argon2id; refresh tokens stored as HMAC-SHA256 hashes; JWT algorithm pinned to HS256; backend avoids custom message crypto | `backend/app/services/password_service.py`, `backend/app/services/token_service.py`, `backend/app/schemas/common.py` |
| Sensitive data exposure | Response schemas omit password hashes and refresh-token hashes; user discovery hides email/key material; audit details are allowlisted; validation errors are sanitized | `backend/app/main.py`, `backend/app/services/audit_service.py`, `backend/tests/security/test_sensitive_data_security.py` |
| Security misconfiguration | `.env.example`; real `.env` ignored; wildcard production CORS rejected; placeholder production secrets rejected; HTTPS enforcement/HSTS controls; PostgreSQL URL scheme enforced | `backend/.env.example`, `backend/.gitignore`, `backend/app/core/config.py`, `backend/app/main.py`, `backend/app/db/session.py`, `backend/tests/integration/test_security_headers.py` |
| Vulnerable components | `pip-audit`, `bandit`, and `ruff` local checks; latest backend virtualenv and requirements audits found no known vulnerabilities | `backend/requirements.txt`, `docs/security/vulnerability_report.md`, `docs/security/security_test_results.md` |
| Rate-limit abuse | Fixed-window in-memory rate limits for register, login, refresh, key upload/fetch, user lookup, message send/forward/read | `backend/app/core/rate_limit.py`, `backend/app/api/deps.py`, `backend/tests/security/test_rate_limit_security.py` |
| Auditability / repudiation | Best-effort audit logs for auth, key relay, message success, and message denial events | `backend/app/services/audit_service.py`, `backend/app/models/audit_log.py`, `backend/tests/integration/test_audit_logging.py` |
| Blockchain integrity evidence | Automatic pending anchors for sent/forwarded encrypted messages; Keccak record IDs and digests; status/verify APIs without plaintext-on-chain | `backend/app/services/blockchain_anchor_service.py`, `backend/app/core/blockchain_hashing.py`, `backend/app/api/v1/blockchain.py` |
| Network architecture | HTTPS public gateway, Nginx VM listener, FastAPI internal app port, PostgreSQL Docker localhost binding recommendation | `docs/architecture/network_architecture.md`, `docs/deployment/runbook.md` |
| Pentest evidence | pytest security suite, optional TLS probe, optional curl/ZAP checks | `backend/tests/security`, `backend/scripts/check_tls_connection.py`, `docs/security/penetration_testing_plan.md`, `docs/security/security_test_results.md` |

## Important Design Claims

- The backend authenticates and authorizes API use, but client-side cryptography is responsible for encrypting/decrypting message content.
- The backend stores `wire_payload_json` as opaque ciphertext and returns it only to authorized sender/recipient users.
- Message send and forward create pending blockchain anchors automatically, but FastAPI does not call Sepolia or hold blockchain wallet keys.
- The backend cannot prove that a ciphertext cryptographically used a claimed prekey; it only validates that the referenced prekey exists for the recipient device and was previously consumed.
- Public TLS still terminates at the gateway/Nginx layer, while FastAPI can enforce HTTPS/HSTS using `ENFORCE_HTTPS`, `TRUST_X_FORWARDED_PROTO`, and `HSTS_ENABLED`.

## Gaps And Follow-Up Controls

| Gap | Risk | Recommended improvement |
| --- | --- | --- |
| No MFA | Stolen credentials can still be used | Add MFA or WebAuthn for production |
| In-memory rate limiter | Limits do not work across multiple API processes | Use Redis, Nginx, or API gateway rate limiting |
| HTTPS/HSTS flags must be enabled at deploy time | App-level transport hardening is bypassed if production env vars are left at development defaults | Set `ENFORCE_HTTPS=true`, `TRUST_X_FORWARDED_PROTO=true`, and `HSTS_ENABLED=true` behind the TLS gateway |
| Uvicorn service template binds `0.0.0.0` | Port `8000` could be exposed if firewall/Nginx are misconfigured | Bind `127.0.0.1` or firewall `8000` |
| Dependency scan evidence can go stale | Vulnerable packages may be missed after dependency changes | Re-run `pip-audit` immediately before submission |
| No admin audit viewer | Audit records require DB/operator access | Add RBAC-protected audit viewer if needed |
| No blockchain confirmation worker in backend package | Pending anchors remain pending until a separate process writes to Sepolia and updates DB status | Implement a worker that reads pending anchors, calls the contract, and records transaction metadata |
| Demo Solidity contract permits unrestricted writes/updates | Anyone could write/update records if deployed as-is | Restrict writes to a worker wallet and consider write-once records for final deployment |
