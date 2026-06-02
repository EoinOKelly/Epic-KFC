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

Use the SSH details provided for the team VM:

```bash
ssh <user>@<vm-hostname-or-ip>
```

Do not paste real private keys, passwords, or tokens into docs.

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

Recommended when Nginx proxies to localhost:

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

Security note: the installer currently writes Uvicorn as `--host 0.0.0.0 --port 8000`. For the documented architecture, change the generated service to `--host 127.0.0.1 --port 8000` or firewall port `8000`.

Edit service:

```bash
sudo systemctl edit --full epic-messaging-api
sudo systemctl daemon-reload
sudo systemctl restart epic-messaging-api
```

## Nginx Checks

Check listener:

```bash
sudo ss -tulpn | grep ':80'
```

Inspect relevant config:

```bash
sudo nginx -T | grep -n "server_name\|proxy_pass\|listen"
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

Recommended binding:

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

TLS probe:

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
.venv/bin/python scripts/check_tls_connection.py kfc.theburkenator.com --port 443
```

## Test Commands On VM

```bash
cd ~/epic_project/Epic-KFC/server/backend
source .venv/bin/activate
ruff check app tests alembic
python -m compileall app tests alembic
pytest tests/security -vv
pytest tests/unit tests/integration tests/security -q
```

Dependency scan before submission:

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
