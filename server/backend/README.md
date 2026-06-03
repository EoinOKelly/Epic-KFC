# Secure Messaging API Backend

FastAPI backend for the CS4455 Epic KFC secure messaging project.

The backend authenticates users, issues short-lived JWT access tokens, rotates refresh tokens, stores public device keys and public one-time prekeys, relays encrypted direct 1:1 message payloads, enforces object-level access control, creates blockchain fidelity anchors, records audit events, and applies API rate limits.

The backend is a ciphertext relay. It does not decrypt messages, store plaintext message bodies, store private keys, store Signal ratchet/session state, or submit Sepolia transactions from FastAPI request handlers. Sepolia submission is handled by the separate backend blockchain worker.

Public API documentation:

```text
https://kfc.theburkenator.com/docs
```

## Tech Stack

| Area | Technology |
| --- | --- |
| API | Python 3.12+, FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| Database | PostgreSQL, `asyncpg`, async SQLAlchemy 2.x |
| Migrations | Alembic |
| Passwords | Argon2id through `argon2-cffi` |
| Tokens | JWT access tokens through `PyJWT`; HMAC-hashed refresh tokens |
| Blockchain metadata | Ethereum Keccak through `eth-hash[pycryptodome]` |
| Blockchain submission | Separate `web3` worker process |
| Tests/checks | pytest, httpx ASGI transport, ruff, bandit, pip-audit |

## Runtime Shape

```text
Client
  -> HTTPS https://kfc.theburkenator.com
  -> TLS gateway
  -> VM port 80
  -> Nginx
  -> http://127.0.0.1:8000 FastAPI/Uvicorn
  -> postgresql+asyncpg://127.0.0.1:5432 PostgreSQL

Blockchain worker
  -> PostgreSQL pending anchors
  -> Sepolia RPC
  -> MessageFidelity contract
  -> confirmation metadata in PostgreSQL
```

## Environment

Create a local environment file from the example:

```bash
cd server/backend
cp .env.example .env
```

Important variables:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://secure_app_user:<database-password>@localhost:5432/secure_messages
TEST_DATABASE_URL=postgresql+asyncpg://secure_app_test_user:<test-database-password>@localhost:5432/secure_messages_test
JWT_SECRET_KEY=<jwt-secret>
REFRESH_TOKEN_HASH_SECRET=<refresh-token-hash-secret>
ENFORCE_HTTPS=false
TRUST_X_FORWARDED_PROTO=false
HSTS_ENABLED=true
ALLOWED_ORIGINS=["http://localhost:3000"]
BLOCKCHAIN_WORKER_ENABLED=false
SEPOLIA_RPC_URL=<sepolia-rpc-url>
DEPLOYER_PRIVATE_KEY=<sepolia-worker-private-key>
MESSAGE_FIDELITY_ADDRESS=<message-fidelity-contract-address>
```

Production settings reject weak or placeholder JWT/refresh-token secrets and wildcard CORS origins. Real `.env` files are ignored by git.

Do not commit or screenshot real secrets, database passwords, Sepolia RPC URLs, wallet private keys, raw refresh tokens, or private messages.

## Local PostgreSQL

Start a local PostgreSQL container:

```bash
docker run --name epic-postgres \
  -e POSTGRES_DB=secure_messages \
  -e POSTGRES_USER=secure_app_user \
  -e POSTGRES_PASSWORD=<database-password> \
  -p 127.0.0.1:5432:5432 \
  -d postgres:16
```

Create a separate test database for integration/security tests:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages
```

```sql
CREATE DATABASE secure_messages_test;
CREATE USER secure_app_test_user WITH PASSWORD '<test-database-password>';
GRANT ALL PRIVILEGES ON DATABASE secure_messages_test TO secure_app_test_user;
```

The integration fixture refuses to run if `TEST_DATABASE_URL` equals `DATABASE_URL` or the test database name does not contain `test`.

## Local Setup

```bash
cd server/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Local docs:

```text
http://127.0.0.1:8000/docs
```

## VM Deployment

The final VM deployment uses systemd services and Nginx:

```text
epic-messaging-api
epic-messaging-blockchain-worker
```

Install/update API service:

```bash
cd ~/epic_project/Epic-KFC
bash server/backend/deploy/install-api-service.sh
```

Install/update Nginx reverse proxy:

```bash
bash server/backend/deploy/install-nginx-api-config.sh
```

Install/update blockchain worker:

```bash
bash server/backend/deploy/install-blockchain-worker-service.sh
```

Check services:

```bash
sudo systemctl status epic-messaging-api
sudo systemctl status epic-messaging-blockchain-worker
sudo systemctl status nginx
```

Expected deployment bindings:

```bash
sudo ss -tulpn | grep ':80'
sudo ss -tulpn | grep ':8000'
sudo ss -tulpn | grep ':5432'
```

Expected result:

- `:80` is the Nginx listener for gateway-forwarded traffic.
- `:8000` is Uvicorn bound to `127.0.0.1`.
- `:5432` is PostgreSQL bound to `127.0.0.1`.

Check Nginx proxy and edge rate limits:

```bash
sudo nginx -t
sudo nginx -T | grep -n "server_name\|proxy_pass\|listen\|limit_req\|client_max_body_size"
```

Check public HTTPS:

```bash
curl -I https://kfc.theburkenator.com/docs
```

Check certificate-verified TLS:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
.venv/bin/python scripts/check_tls_connection.py kfc.theburkenator.com --port 443
```

Check migrations:

```bash
alembic current
alembic upgrade head
alembic current
```

Expected final revision:

```text
20260602_0003 (head)
```

## API Areas

| Area | Endpoints |
| --- | --- |
| Auth | `/api/v1/auth/register`, `/login`, `/refresh`, `/logout`, `/me` |
| Users | `/api/v1/users/by-username/{username}` |
| Keys | `/api/v1/keys/devices/{device_id}`, one-time prekeys, prekey bundle |
| Messages | send, received, sent, fetch, forward, revoke, delete |
| Anchors | message anchor status, anchor create/reuse, anchor status by ID, metadata verify |

The full API contract is in:

```text
../docs/api/api_contract.pdf
```

## Blockchain Anchoring

Message send and forward create a pending `blockchain_anchors` row in the same database transaction as the encrypted message.

Backend-generated fields:

- `record_id = keccak256("message:" + message_id)`
- `digest = keccak256(canonical encrypted message record)`

The canonical record includes IDs, device IDs, timestamps, forwarding lineage, and the opaque encrypted `wire_payload_json`. It does not include plaintext, private keys, raw tokens, or client ratchet state.

The worker submits pending anchors to Sepolia and updates:

- `status`
- `transaction_hash`
- `contract_address`
- `anchored_at`

Run one worker batch locally:

```bash
cd server/backend
source .venv/bin/activate
python -m app.workers.blockchain_worker --once
```

Run continuously:

```bash
python -m app.workers.blockchain_worker
```

Check recent anchor rows:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages
```

```sql
SELECT id, message_id, record_id, digest, status, transaction_hash, contract_address, anchored_at
FROM blockchain_anchors
ORDER BY created_at DESC
LIMIT 20;
```

Pending anchors contain `status = pending` with no transaction hash. Confirmed anchors contain `status = confirmed`, a `0x...` transaction hash, contract address, and anchored timestamp.

## Tests And Checks

Run from `server/backend` with the virtualenv active:

```bash
ruff check app tests alembic scripts
python -m compileall app tests scripts alembic
bandit -q -r app scripts
pip-audit --progress-spinner off
pip-audit --progress-spinner off -r requirements.txt
pytest tests/unit tests/integration tests/security -q
```

Final local evidence recorded:

```text
327 passed in 16.50s
```

The full evidence record is in:

```text
../docs/security/security_test_results.pdf
```

## Security Summary

- Passwords are stored as Argon2id hashes.
- Refresh tokens are stored as HMAC-SHA256 hashes, not raw tokens.
- Access tokens are signed JWTs with required claims.
- Protected routes load an active current user from the Bearer token.
- Message and anchor access is checked at object level.
- Request schemas reject extra fields and sensitive/plaintext/private-key fields.
- Validation errors are sanitized.
- Repositories use SQLAlchemy ORM expressions.
- Nginx provides public edge rate limits; FastAPI provides route/user rate limits.
- Public clients use HTTPS; the C++ client real mode requires HTTPS and keeps certificate validation active.
- Uvicorn and PostgreSQL bind to localhost in the deployment model.
- FastAPI creates pending anchors; the worker submits them to Sepolia.

## Documentation Map

| Document | Path |
| --- | --- |
| Backend architecture | `../docs/architecture/backend_architecture.pdf` |
| Network architecture | `../../docs/network_docs/network_architecture.pdf` |
| API contract | `../docs/api/api_contract.pdf` |
| Database design | `../docs/database/database_design.pdf` |
| Security controls mapping | `../docs/security/security_controls_mapping.pdf` |
| Backend threat model | `../docs/security/backend_threat_model.pdf` |
| Security test results | `../docs/security/security_test_results.pdf` |
| AI prompt artefact | `../docs/ai/backend_prompts_daniel.md` |

