#!/usr/bin/env bash
# Install Epic Messaging API as a systemd service (24/7 on the VM).
#
# Run on the VM from anywhere inside the repo:
#   bash server/backend/deploy/install-api-service.sh
#
# Requires: sudo, python venv at server/backend/.venv, server/backend/.env

set -euo pipefail

SERVICE_NAME="epic-messaging-api"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/../.." && pwd)"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn)}"
UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ ! -x "${BACKEND_DIR}/.venv/bin/uvicorn" ]]; then
  echo "error: missing ${BACKEND_DIR}/.venv/bin/uvicorn"
  echo "Run: cd ${BACKEND_DIR} && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "${BACKEND_DIR}/.env" ]]; then
  echo "error: missing ${BACKEND_DIR}/.env"
  echo "Run: cp ${BACKEND_DIR}/.env.example ${BACKEND_DIR}/.env && edit credentials"
  exit 1
fi

echo "Installing ${SERVICE_NAME} for user ${SERVICE_USER}"
echo "  backend: ${BACKEND_DIR}"

sudo tee "${UNIT_PATH}" > /dev/null <<EOF
[Unit]
Description=Epic Messaging FastAPI backend
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo
echo "Service installed. Status:"
sudo systemctl status "${SERVICE_NAME}" --no-pager || true
echo
echo "Useful commands:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo "  sudo systemctl restart ${SERVICE_NAME}   # after git pull + pip install"
