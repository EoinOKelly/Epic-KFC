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

