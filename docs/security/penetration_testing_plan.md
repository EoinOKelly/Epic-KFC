# Project Penetration Testing Plan

Date documented: 2026-06-03

Scope: C++ Qt client, FastAPI backend, PostgreSQL database, blockchain worker, Solidity contract, Sepolia deployment, and standalone verification UI.

This plan tests the secure messaging project as an integrated system. The aim is to show that a user can safely authenticate, exchange encrypted messages, and verify message fidelity without exposing plaintext or allowing unauthorised access.

## In Scope

- C++ client startup modes, command parsing, HTTPS enforcement, certificate validation, authentication flow, encrypted local state, message operations, and `/verify`.
- Backend authentication, refresh tokens, authorisation, schemas, message routes, key/prekey routes, blockchain verification routes, and download/delete/revoke behaviour where implemented.
- PostgreSQL deployment posture, schema constraints, stored message data, anchor rows, and transaction hash format.
- Blockchain worker queue processing, Sepolia submission, confirmation handling, retry/failure behaviour, and logs.
- Solidity contract behaviour for storing message or conversation digests.
- Standalone verification UI behaviour for valid records, mismatched content, pending anchors, and invalid transaction hashes.
- Dependency and static-analysis checks for backend, C++ client, and blockchain packages.

## Out Of Scope

- Attacks against real third-party services such as Alchemy, GitHub, Sepolia infrastructure, or the public CA ecosystem.
- Mainnet Ethereum testing.
- Destructive production database tests.
- Brute-force password attacks against real users.
- Attempts to extract private keys from real wallets.
- Formal verification of the Solidity contract.
- Social engineering or phishing.

## Test Environments

| Environment | Purpose |
| --- | --- |
| Local backend test environment | FastAPI route tests, schema validation, auth, authorisation, security unit tests |
| Local C++ build | Client parser, TLS mode checks, crypto checks, local state encryption checks |
| Local blockchain project | Hardhat contract tests and verification UI checks |
| Production VM | HTTPS deployment, PostgreSQL Docker posture, systemd worker status, real Sepolia anchoring |
| Sepolia testnet | Real blockchain transaction evidence using test ETH |

## Tools

| Tool | Use |
| --- | --- |
| `pytest` | Backend unit, integration, and security tests |
| `ruff` | Backend lint checks |
| `bandit` | Backend Python static security scan |
| `pip-audit` | Backend Python dependency vulnerability scan |
| `cmake` / client test binary | C++ client build and security-relevant tests |
| `npm test` / Hardhat | Solidity contract tests |
| `npm audit` | Blockchain and verification UI dependency scan |
| `curl` or `httpie` | Manual API probing |
| `docker exec psql` | Database inspection on the VM |
| `systemctl` / `journalctl` | Blockchain worker service checks |
| Browser or verification UI | Manual fidelity verification |

## Test Categories

| Category | Components | What to test | Expected result |
| --- | --- | --- | --- |
| Authentication | Client, backend | Signup, login, refresh, logout, invalid credentials, expired token | Valid users can authenticate; invalid or expired credentials are rejected |
| Authorisation | Client, backend, DB | Read, download, revoke, delete, forward, and verify records owned by another user | Cross-user access is rejected |
| Transport security | Client, backend, Nginx | Client real mode requires HTTPS; certificate validation remains enabled | Plain HTTP or invalid TLS is rejected in real mode |
| Input validation | Client, backend, blockchain routes | Bad UUIDs, malformed JSON, oversized fields, invalid transaction hashes, bad digest formats | API returns clear 4xx errors without crashes |
| SQL injection | Backend, DB | Injection strings in login, search/list filters, message IDs, user IDs | Inputs are treated as values, not SQL |
| Local data protection | C++ client | Inspect local state files after login and key generation | Tokens and private keys are encrypted at rest |
| Message confidentiality | Client, backend, DB | Send messages and inspect API/database storage | Backend and DB store ciphertext, not plaintext message bodies |
| Message integrity | Client, backend, verification UI | Tamper with ciphertext, digest, or verification input | Tampering causes decrypt or verification failure |
| Prekey handling | Client, backend | Use missing, stale, or consumed one-time prekeys | Backend rejects inconsistent prekey consumption |
| Blockchain anchoring | Backend, worker, contract, DB | Send message, create pending anchor, worker confirms it on Sepolia | Anchor becomes confirmed with `0x` transaction hash |
| Blockchain failure handling | Worker, backend, client | Stop worker or remove RPC/wallet config | Messages still send; anchors remain pending or failed, not falsely confirmed |
| Contract integrity | Solidity, worker | Duplicate record IDs, non-owner calls, invalid digests | Final contract rejects unauthorised or overwrite attempts |
| Metadata exposure | Backend, DB, blockchain | Review response bodies, logs, chain data | Only required metadata is exposed; plaintext and secrets are absent |
| Dependency risk | Backend, client, blockchain | Run dependency scanners | Known vulnerabilities are fixed or documented |
| Logging | Backend, worker, client | Trigger errors and inspect logs | Logs do not expose tokens, private keys, passwords, or plaintext messages |

## Client-Driven End-To-End Demo Flow

This is the primary evidence path for the demo. Drive the system from the C++ client and use screenshots from the client, database, worker logs, Sepolia transaction pages, and verification UI as proof.

### Setup Checks

Run these before recording evidence:

```bash
cd /home/student/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
docker port epic-postgres 5432
alembic current
curl -I https://kfc.theburkenator.com/docs
```

Expected:

- `docker port epic-postgres 5432` returns `127.0.0.1:5432`, not `0.0.0.0:5432`.
- Alembic reports the latest migration.
- The public `/docs` endpoint is reachable over HTTPS without certificate errors.

### Client Flow

Use two test users, for example `aliceDemo` and `bobDemo`, on the real HTTPS backend.

1. Start the C++ client in real mode with the public HTTPS URL.
2. Register or log in as `aliceDemo`.
3. Confirm device keys upload successfully.
4. Register or log in as `bobDemo` in a second client/session/device.
5. Confirm device keys and one-time prekeys upload successfully.
6. From `aliceDemo`, run `/trust bobDemo` if the client requires trust before sending.
7. Send a message from `aliceDemo` to `bobDemo`.
8. From `bobDemo`, run `/inbox` and `/read aliceDemo`; confirm the message decrypts.
9. Reply from `bobDemo` to `aliceDemo`.
10. Forward one accessible message to the other user with `/forward <messageId> <username>`.
11. Run `/verify <messageId>` for at least one message after the worker confirms its anchor.
12. Open the standalone verification UI and verify the same message/digest/transaction evidence.
13. Logout and try an authenticated command; confirm the client/backend reject it.

Expected:

- Client uses `https://kfc.theburkenator.com/api/v1`.
- HTTP URLs are rejected in real mode.
- The backend returns `201` for send/forward and `200` for successful reads/verifications.
- The receiver can decrypt; the server/database cannot show plaintext.
- Blockchain anchor starts pending and later becomes confirmed with a Sepolia transaction hash.
- Verification passes for matching evidence and fails for tampered content/digest.

### Failure Checks From The Client

Run these during or after the happy path:

| Test | Client action | Expected result |
| --- | --- | --- |
| Invalid login | Wrong password | Clear auth failure, no token stored |
| Missing auth | Logout then `/inbox` | Command fails or backend returns `401` |
| Wrong user access | User A verifies/downloads/deletes User B-only message ID | `404` or `403`; no plaintext |
| Invalid forward | Forward a non-existent or uncached message ID | Client shows failure; backend does not create a row |
| Backend/DB outage | Stop backend or DB, then send/forward | Client shows network/server error, not silent success |
| Bad transaction hash | Verification UI input with wrong length/non-hex hash | Validation failure |
| Tampered verification | Change one character in verified content/digest | Verification reports mismatch |

## Screenshot Evidence Pack

Capture screenshots with timestamps or command prompts visible. Do not include private keys, wallet seed phrases, API keys, JWTs, refresh tokens, real passwords, or `.env` contents.

| Screenshot | Evidence shown | Rubric value |
| --- | --- | --- |
| Client startup | Real mode uses `https://kfc.theburkenator.com/api/v1` | SSL/TLS protected frontend connection |
| Browser or `curl -I` public URL | HTTPS virtual host reachable without certificate error | Secure connectivity and certificate validity |
| Client register/login | Authenticated user flow | Server-side authentication |
| Client send/read | Receiver decrypts, sender/receiver workflow works end to end | Functional secure messaging |
| Client failed invalid auth/access | Invalid credentials or cross-user message blocked | Broken authentication/access control checked |
| Client `/forward` result | Forward creates a new message ID or clear failure | Message workflow and error handling |
| Client `/verify` result | Confirmed anchor verifies successfully | Blockchain fidelity proof |
| Verification UI success/failure | Matching evidence passes and tampered evidence fails | Integrity verification |
| PostgreSQL `messages` query | Message rows contain `wire_payload_json`, not plaintext body columns | Sensitive data exposure and confidentiality |
| PostgreSQL `blockchain_anchors` query | `status`, `record_id`, `digest`, `transaction_hash`, `anchored_at` | Database evidence for blockchain anchor |
| Sepolia explorer transaction | Same `0x...` transaction hash as DB | External transaction hash evidence |
| Worker log | Pending anchor processed to confirmed or failed safely | Blockchain worker behaviour |
| Backend unit test output | Unit tests passed | Implemented controls tested |
| Backend security/static scan output | `ruff`, `bandit`, `pip-audit` results | Vulnerable components and secure coding evidence |

Useful database screenshot queries:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages -c "SELECT id, sender_user_id, recipient_user_id, created_at, left(wire_payload_json, 80) AS encrypted_preview FROM messages ORDER BY created_at DESC LIMIT 10;"
```

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages -c "SELECT message_id, record_id, digest, status, transaction_hash, contract_address, chain_id, anchored_at FROM blockchain_anchors ORDER BY created_at DESC LIMIT 10;"
```

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages -c "SELECT message_id, transaction_hash FROM blockchain_anchors WHERE transaction_hash IS NOT NULL AND transaction_hash !~ '^0x[0-9a-fA-F]{64}$';"
```

Expected result for the final query: no rows.

## Backend Unit Test Evidence

Assume the backend unit tests pass and include the terminal screenshot/output in the final evidence pack. Do not re-run destructive database tests during the demo unless the test database is known-good.

Run from `server/backend`:

```bash
source .venv/bin/activate
pytest tests/unit -q
```

| Unit test file | Controls covered | Rubric points supported |
| --- | --- | --- |
| `tests/unit/test_password_service.py` | Argon2id PHC hashes, random salts, password verification, malformed hash safety, rehash detection | Secure coding, passwords not visible, hashes protected |
| `tests/unit/test_token_service.py` | JWT claims, expiry, malformed/wrong-signature/wrong-type rejection, refresh-token entropy, HMAC refresh-token hashes, algorithm pinning | Broken authentication, cryptographic issues, sensitive data exposure |
| `tests/unit/test_rate_limit.py` | Fixed-window limits, retry-after, per-user/per-IP key separation, disabled limiter behaviour, state clearing | API abuse, brute-force mitigation |
| `tests/unit/test_wire_payload_validation.py` | LibSignal wire payload shape, missing body rejection, legacy payload rejection, forbidden plaintext key rejection | Improper input validation, sensitive data exposure, cryptographic boundary |
| `tests/unit/test_tls_connection_probe.py` | Hostname resolution helper, duplicate address handling, empty resolution failure, certificate-name formatting | Network coding, host-name resolution, TLS evidence |
| `tests/unit/test_blockchain_anchor_service.py` | Deterministic `bytes32` record IDs, stable digest derivation, digest changes on ciphertext/provenance changes | Blockchain integrity and tamper evidence |

Additional backend evidence, assuming current suites pass:

- `pytest tests/security -vv` covers auth attacks, access control, validation, injection, sensitive-data leakage, and rate limiting.
- `pytest tests/integration/test_security_headers.py -q` covers security headers, HSTS, HTTPS enforcement, trusted proxy signalling, CORS hardening, and production secret validation.
- `bandit -q -r app scripts` covers Python static security review.
- `pip-audit` and `pip-audit -r requirements.txt` cover vulnerable Python components.

## Rubric Coverage Matrix

| Brief/rubric area | Evidence to show | Coverage level |
| --- | --- | --- |
| Secure connectivity between client and server | Client real mode HTTPS URL, public `/docs` HTTPS screenshot, TLS probe output | Covered |
| Client verifies SSL certificate | Qt real mode without disabled certificate validation; browser/curl no certificate error; optional TLS probe | Covered, explain Qt uses platform CA validation |
| Server-side security and authentication | Login/logout screenshots, JWT/auth unit tests, auth security tests | Covered |
| Users authenticated and authorised | Cross-user access failure, `/auth/me`, message read/verify ownership checks | Covered |
| Vulnerability/pentest report | This plan plus screenshots and test outputs | Covered |
| Network architecture documentation | `docs/architecture/network_architecture.md`, DB binding screenshot, Nginx/gateway notes | Covered |
| External services documented | PostgreSQL, Sepolia, worker, virtual host/gateway documented | Covered |
| Frontend creates SSL protected connection to virtual host | Client startup and public HTTPS screenshots | Covered |
| Backend accepts and processes requests | `/docs`, auth, send/read/forward/verify screenshots and backend logs | Covered |
| Resolve host names/open socket connections | TLS probe unit test and script; C++ client uses Qt network stack | Partially covered; excellent answer should explain Qt/libcurl-style abstraction or show low-level socket demo |
| Partial reads/writes/error return values | Client HTTP gateway error handling screenshots; code review of `QNetworkReply` paths | Partially covered unless a low-level socket demo is added |
| Improper input validation | Invalid UUID/hash/payload screenshots; wire payload unit tests | Covered |
| Broken authentication | Bad login, expired/wrong JWT tests | Covered |
| Broken access control | Cross-user message/verify attempts rejected | Covered |
| Cryptographic issues | Argon2id, HMAC refresh hashes, LibSignal payload validation, OpenSSL-backed client crypto tests | Covered |
| Injection | Security tests and SQLAlchemy repository review | Covered |
| Security misconfiguration | Localhost DB/backend bindings, CORS/HSTS/HTTPS config tests, dependency scans | Covered |
| Sensitive data exposure | DB screenshots show ciphertext only; audit/log checks; no plaintext/private keys in screenshots | Covered |
| Vulnerable components | `pip-audit`, `npm audit`, dependency screenshots | Covered if recorded immediately before submission |

## Backend Commands

Run from `server/backend`:

```bash
source .venv/bin/activate
ruff check app tests alembic
python -m compileall app tests alembic
pytest tests/security -vv
pytest tests/unit tests/integration tests/security -q
bandit -r app
pip-audit
```

TLS probe, if the deployment check script is available:

```bash
python scripts/check_tls_connection.py kfc.theburkenator.com --port 443
```

## C++ Client Commands

Run from the repository root, adjusting the build directory for the host platform:

```bash
cmake -S client -B client/out/build/linux-debug -G Ninja -DCLIENT_BUILD_TESTS=ON
cmake --build client/out/build/linux-debug
client/out/build/linux-debug/client_tests
```

On the Windows/MinGW build used by the team, the test binary path may be:

```bash
client/out/build/mingw-debug/client_tests.exe
```

Manual client checks:

- Start in real mode and confirm the backend URL is HTTPS.
- Attempt to use an HTTP backend URL and confirm the client refuses it.
- Log in, send a message, list messages, forward if implemented, revoke/delete if implemented, and run `/verify <messageId>`.
- Inspect the local state file and confirm tokens and private keys are not stored as readable plaintext.
- Use `--debug` only for mock-mode demonstrations, not as evidence of production security.

## Blockchain Commands

Run from `blockchain`:

```bash
npm install
npm test
npm run build
npm audit
```

If the project uses a different compile script, run the Hardhat compile command directly:

```bash
npx hardhat compile
```

Manual blockchain checks:

- Confirm the final contract address in documentation matches the backend `MESSAGE_FIDELITY_ADDRESS`.
- Confirm the final contract source is owner-only/write-once.
- Confirm the backend worker wallet is the only account expected to call `storeHash`.
- Confirm no plaintext message content is sent to the contract.
- Confirm the verification UI handles successful match, mismatch, pending anchor, and invalid input.

## Production VM Checks

Worker status:

```bash
sudo systemctl status epic-messaging-blockchain-worker
sudo journalctl -u epic-messaging-blockchain-worker -f
```

Run one worker batch manually:

```bash
cd /home/student/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
python -m app.workers.blockchain_worker --once
```

Check pending and confirmed anchors:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages -c "SELECT id, status, transaction_hash, anchored_at FROM blockchain_anchors ORDER BY created_at DESC LIMIT 10;"
```

Check transaction hash format:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages -c "SELECT id, transaction_hash FROM blockchain_anchors WHERE transaction_hash IS NOT NULL AND transaction_hash !~ '^0x[0-9a-fA-F]{64}$';"
```

Expected result: the second query returns no rows.

## Manual API Probes

Use a test account only.

Examples:

- Send unauthenticated requests to protected routes and confirm `401`.
- Use a valid token for user A against user B's message IDs and confirm `403` or `404`.
- Submit invalid UUIDs to message and verification routes and confirm `422`.
- Submit transaction hashes without `0x`, with non-hex characters, or with the wrong length and confirm validation rejects them.
- Try oversized message fields and confirm the API rejects or safely handles them.
- Confirm error bodies do not include stack traces, secrets, or database details.

## Verification Flow Test

1. Send a message from the C++ client.
2. Confirm the backend creates a pending blockchain anchor.
3. Confirm the worker changes the anchor to confirmed.
4. Confirm the database stores `contract_address`, `chain_id`, `transaction_hash`, and `anchored_at`.
5. Run `/verify <messageId>` in the C++ client.
6. Open the standalone verification UI and verify the same message content or digest.
7. Change one character in the verification input and confirm the UI reports failure.

Expected result: correct content passes, modified content fails, and pending anchors are shown as pending rather than as failed integrity.

## Evidence To Record

Record exact commands, dates, commit hashes, and short outcomes for:

- Backend test run.
- Backend static analysis and dependency scan.
- C++ client build and client test run.
- Blockchain Hardhat test run.
- Blockchain deployment address and Sepolia transaction evidence.
- Worker service status and one confirmed anchor log line.
- Database query showing valid `0x` transaction hash format.
- Verification UI pass/fail screenshots.
- Any failed test and the fix applied.

Do not record private keys, seed phrases, API keys, database passwords, JWTs, real user messages, or `.env` contents.

## Pass Criteria

The project passes this penetration testing plan when:

- The C++ client enforces HTTPS in real mode and protects local secrets at rest.
- Backend authentication and authorisation reject unauthorised access.
- Message plaintext is not visible in backend storage, database rows, logs, or blockchain records.
- Blockchain anchors are created by the worker and confirmed on Sepolia.
- Verification succeeds only for matching content/digests.
- Dependency and static-analysis issues are fixed or clearly documented.
- Remaining limitations are stated honestly in the final submission material.
