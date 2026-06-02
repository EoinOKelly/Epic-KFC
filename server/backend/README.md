# Secure Messaging API Backend

FastAPI backend for the Epic KFC secure messaging project. The backend authenticates users, issues short-lived access tokens, rotates refresh tokens, stores public device key material, stores public one-time prekeys, relays encrypted direct 1:1 message payloads, enforces object-level access control, creates pending blockchain integrity anchors, records audit events, and applies basic rate limiting.

The backend is an opaque relay. It does not decrypt messages, store plaintext message bodies, store private keys, store Signal ratchet/session state, or submit blockchain transactions from FastAPI request handlers.

Public backend documentation URL:

```text
https://kfc.theburkenator.com/docs
```

## Tech Stack

- Python 3.12+ / FastAPI / Uvicorn
- Pydantic v2 request and response validation
- Async SQLAlchemy 2.x
- PostgreSQL with `asyncpg`
- Alembic migrations
- Argon2id password hashing through `argon2-cffi`
- JWT access tokens through `PyJWT`
- Ethereum Keccak hashing through `eth-hash[pycryptodome]`
- pytest, httpx ASGI transport, ruff, bandit, pip-audit

## Environment Variables

Copy the example file and edit the secrets and database credentials:

```bash
cd server/backend
cp .env.example .env
```

Required or important variables:

```dotenv
APP_NAME=Secure Messaging API
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://secure_app_user:change_me@localhost:5432/secure_messages
TEST_DATABASE_URL=postgresql+asyncpg://secure_app_test_user:change_me@localhost:5432/secure_messages_test
LOG_LEVEL=INFO
JWT_SECRET_KEY=change_me_local_dev_only
REFRESH_TOKEN_HASH_SECRET=change_me_refresh_hash_secret_local_only
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
RATE_LIMIT_ENABLED=true
SECURITY_HEADERS_ENABLED=true
ENFORCE_HTTPS=false
TRUST_X_FORWARDED_PROTO=false
HSTS_ENABLED=true
HSTS_MAX_AGE_SECONDS=31536000
ALLOWED_ORIGINS=["http://localhost:3000"]
CORS_ALLOW_CREDENTIALS=false
```

Do not commit a real `.env`. The backend `.gitignore` excludes `.env`, `.env.local`, and `.env.*` while keeping `.env.example`.

## Docker PostgreSQL Setup

The backend requires PostgreSQL and rejects non-PostgreSQL database URLs. A local Docker setup can be started with:

```bash
docker run --name epic-postgres \
  -e POSTGRES_DB=secure_messages \
  -e POSTGRES_USER=secure_app_user \
  -e POSTGRES_PASSWORD=change_me \
  -p 127.0.0.1:5432:5432 \
  -d postgres:16
```

Create a test database and test user if running the integration/security suite:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages
```

Example SQL for local development:

```sql
CREATE DATABASE secure_messages_test;
CREATE USER secure_app_test_user WITH PASSWORD 'change_me';
GRANT ALL PRIVILEGES ON DATABASE secure_messages_test TO secure_app_test_user;
```

PostgreSQL should be bound to `127.0.0.1:5432` for the project deployment, not exposed on a public interface.

## Local Setup

```bash
cd server/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run migrations:

```bash
alembic upgrade head
```

Run FastAPI locally:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs are then available at:

```text
http://127.0.0.1:8000/docs
```

## VM Run Commands

Manual VM restart command:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
pkill -f "uvicorn app.main:app"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
```

There is also a systemd installer at `deploy/install-api-service.sh`. If the VM uses Nginx as the public HTTP listener, bind Uvicorn to `127.0.0.1:8000` or firewall port `8000` so FastAPI is not exposed directly.

Install or update the Nginx reverse proxy and edge rate limits on the VM:

```bash
cd ~/epic_project/Epic-KFC
bash server/backend/deploy/install-nginx-api-config.sh
```

Nginx handles coarse IP-based abuse limits before requests reach Python. FastAPI still keeps authenticated per-user limits for actions such as message send, forward, and key upload.

## Tests And Checks

Run static checks:

```bash
ruff check app tests alembic
python -m compileall app tests alembic
```

Run security tests:

```bash
pytest tests/security -vv
```

Run the full backend suite:

```bash
pytest tests/unit tests/integration tests/security -q
```

The integration and security tests require `TEST_DATABASE_URL` to point at a migrated PostgreSQL database whose name contains `test`. The fixture refuses to run if `TEST_DATABASE_URL` equals `DATABASE_URL`.

## Blockchain Anchoring

Message send and forward flows automatically create a pending `blockchain_anchors` row in the same database transaction as the new encrypted message. The backend computes:

- `record_id = keccak256("message:" + message_id)`
- `digest = keccak256(canonical encrypted message record)`

The canonical record contains message IDs, sender/recipient IDs, device IDs, timestamp, and the opaque encrypted `wire_payload_json`. It does not contain plaintext, private keys, raw tokens, or client ratchet state.

Available blockchain metadata endpoints:

- `GET /api/v1/messages/{message_id}/anchor`
- `POST /api/v1/blockchain/anchors`
- `GET /api/v1/blockchain/anchors/{anchor_id}`
- `POST /api/v1/blockchain/verify`

FastAPI does not call Sepolia, hold a wallet private key, or call the Solidity contract directly. A separate worker/script still needs to read pending anchors, call the blockchain contract, and update `transaction_hash`, `contract_address`, `status`, and `anchored_at`.

## Documentation Map

- Backend architecture: `../docs/architecture/backend_architecture.md`
- Network architecture: `../docs/architecture/network_architecture.md`
- API contract: `../docs/api/api_contract.md`
- Database design: `../docs/database/database_design.md`
- Security controls mapping: `../docs/security/security_controls_mapping.md`
- Threat model: `../docs/security/threat_model.md`
- Penetration testing plan: `../docs/security/penetration_testing_plan.md`
- Security test results: `../docs/security/security_test_results.md`
- Vulnerability report: `../docs/security/vulnerability_report.md`
- Operations runbook: `../docs/deployment/runbook.md`

## Known Limitations

- No MFA.
- FastAPI in-memory rate limiting is single-process only; the provided Nginx config adds VM edge IP limits.
- Refresh sessions are stored in PostgreSQL rather than Redis.
- FastAPI does not currently terminate TLS itself; public HTTPS is provided by the gateway/proxy layer.
- The backend stores and returns opaque encrypted `wire_payload_json` to authorized users, but cannot prove cryptographically that a payload used a claimed one-time prekey.
- Blockchain anchoring currently creates pending database evidence automatically, but the Sepolia submission/confirmation worker is still a separate missing deployment piece.
- There is no admin audit-log viewer route.
