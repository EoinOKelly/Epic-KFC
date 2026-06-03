# Backend Operations Runbook

This runbook covers common VM/backend operations for the FastAPI server, Nginx proxy, and PostgreSQL Docker container.

## Paths

Expected VM project path:

```text
~/epic_project/Epic-KFC/server/backend
```

Backend package path in this repository:

```text
server/backend
```

Public backend URL:

```text
https://kfc.theburkenator.com/docs
```

## SSH Into The VM


## Pull Latest Code

```bash
cd ~/epic_project/Epic-KFC
git status --short
git pull
```

If dependencies changed:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Check

```bash
cd ~/epic_project/Epic-KFC/server/backend
test -f .env
source .venv/bin/activate
python -c "from app.core.config import settings; print(settings.app_name, settings.app_env)"
```

Check the database URL scheme without printing secrets:

```bash
python -c "from app.core.config import settings; print(settings.database_url.split('@')[-1] if settings.database_url else 'missing')"
```

## Run Migrations

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
alembic current
alembic upgrade head
alembic current
```

## Manual Backend Restart

Manual restart command for the Nginx-to-localhost deployment:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
pkill -f "uvicorn app.main:app"
nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
```

View logs:

```bash
tail -f backend.log
```

Check process:

```bash
ps aux | grep uvicorn
```

## Systemd Backend Service

The repo includes:

```text
server/backend/deploy/install-api-service.sh
server/backend/deploy/epic-messaging-api.service
```

Install/reinstall:

```bash
bash server/backend/deploy/install-api-service.sh
```

Useful commands:

```bash
sudo systemctl status epic-messaging-api
sudo systemctl restart epic-messaging-api
sudo journalctl -u epic-messaging-api -f
```

Security note: the installer writes Uvicorn as `--host 127.0.0.1 --port 8000`, so Nginx remains the public VM listener.

Edit service:

```bash
sudo systemctl edit --full epic-messaging-api
sudo systemctl daemon-reload
sudo systemctl restart epic-messaging-api
```

## Nginx Checks

Install or update the repo-provided Nginx API proxy with edge rate limits:

```bash
cd ~/epic_project/Epic-KFC
bash server/backend/deploy/install-nginx-api-config.sh
```

This installs `server/backend/deploy/nginx/epic-messaging-api.conf`, tests the Nginx configuration, and reloads Nginx. It is separate from restarting FastAPI.

Check listener:

```bash
sudo ss -tulpn | grep ':80'
```

Inspect relevant config:

```bash
sudo nginx -T | grep -n "server_name\|proxy_pass\|listen\|limit_req"
```

Restart Nginx:

```bash
sudo nginx -t
sudo systemctl restart nginx
```

View errors:

```bash
sudo tail -f /var/log/nginx/error.log
```

Expected proxy shape:

```text
Gateway HTTPS -> VM port 80 -> Nginx -> http://127.0.0.1:8000
```

Expected rate-limit shape:

- Auth register/login: `1r/m` per Nginx client IP with a small burst for short retry/demo flows.
- Refresh: `2r/m` per Nginx client IP with burst.
- Prekey bundle fetch: `60r/m` per Nginx client IP.
- Message send: `120r/m` per Nginx client IP.
- FastAPI still enforces authenticated per-user limits after JWT validation.

If the provided gateway hides the real client IP, configure Nginx real-IP handling only for trusted gateway IPs. Do not trust arbitrary `X-Forwarded-For` values from the public internet.

## PostgreSQL Docker Checks

Check container:

```bash
docker ps
docker logs epic-postgres --tail 100
```

Ensure restart policy:

```bash
bash server/backend/deploy/ensure-postgres-restart.sh epic-postgres
```

Check database port binding:

```bash
sudo ss -tulpn | grep ':5432'
```

Deployment binding:

```text
127.0.0.1:5432
```

## Exposed Port Check

```bash
sudo ss -tulpn | grep ':80'
sudo ss -tulpn | grep ':8000'
sudo ss -tulpn | grep ':5432'
```

Expected:

- `:80` visible for Nginx/gateway traffic.
- `:8000` bound to `127.0.0.1` or firewalled.
- `:5432` bound to `127.0.0.1`.

## API Smoke Tests

Local VM:

```bash
curl -i http://127.0.0.1:8000/docs
curl -i http://127.0.0.1:8000/api/v1/auth/me
```

Public URL:

```bash
curl -I https://kfc.theburkenator.com/docs
```

Nginx rate-limit smoke check for auth abuse:

```bash
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Content-Type: application/json" \
    -d '{"username_or_email":"missing-user","password":"incorrect-password"}' \
    https://kfc.theburkenator.com/api/v1/auth/login
done
```

Expected: early requests return `401`, then repeated requests from the same IP return `429`.

TLS probe:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
.venv/bin/python scripts/check_tls_connection.py kfc.theburkenator.com --port 443
```

## Blockchain Anchor Operations

The FastAPI backend creates pending `blockchain_anchors` rows automatically when direct messages are sent or forwarded. A separate backend worker process submits those pending records to Sepolia and updates confirmation metadata.

Useful database checks:

```bash
docker exec -it epic-postgres psql -U secure_app_user -d secure_messages
```

```sql
SELECT id, message_id, record_id, digest, status, transaction_hash, anchored_at
FROM blockchain_anchors
ORDER BY created_at DESC
LIMIT 20;
```

Expected message-send state before a blockchain worker runs:

```text
status = pending
transaction_hash = NULL
anchored_at = NULL
```

A confirmed row after the worker runs contains:

```text
status = confirmed
transaction_hash = 0x...
contract_address = 0x...
anchored_at = <block timestamp>
```

The backend worker:

1. Read pending anchors from PostgreSQL.
2. Call the Solidity contract with the backend-generated `record_id` and `digest` or future `merkle_root`.
3. Update `status`, `transaction_hash`, `contract_address`, and `anchored_at`.

Configure `server/backend/.env` with:

```dotenv
BLOCKCHAIN_WORKER_ENABLED=true
SEPOLIA_RPC_URL=<sepolia-rpc-url>
DEPLOYER_PRIVATE_KEY=<sepolia-worker-private-key>
MESSAGE_FIDELITY_ADDRESS=<message-fidelity-contract-address>
```

Run one batch manually:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
python -m app.workers.blockchain_worker --once
```

Install the long-running worker service:

```bash
cd ~/epic_project/Epic-KFC
bash server/backend/deploy/install-blockchain-worker-service.sh
sudo journalctl -u epic-messaging-blockchain-worker -f
```

The sibling `blockchain` folder still contains Solidity deployment/demo scripts and the fidelity UI. FastAPI does not call those scripts during request handling.

## Test Commands On VM

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
ruff check app tests alembic
python -m compileall app tests alembic
pytest tests/security -vv
pytest tests/unit tests/integration tests/security -q
```

Dependency scan command:

```bash
pip-audit
```

## Common Failure Checks

Database unavailable:

```bash
docker ps
docker logs epic-postgres --tail 100
alembic current
```

Backend not reachable through Nginx:

```bash
sudo systemctl status nginx
sudo nginx -t
sudo ss -tulpn | grep ':8000'
tail -f backend.log
```

Auth endpoints returning token configuration errors:

```bash
grep -n "JWT_SECRET_KEY\|REFRESH_TOKEN_HASH_SECRET" .env
```

Do not print actual secret values in screenshots or submission documents.
