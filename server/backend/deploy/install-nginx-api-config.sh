#!/usr/bin/env bash
# Install the Epic Messaging Nginx reverse proxy with edge rate limits.
#
# Run from anywhere inside the repo on the VM:
#   bash server/backend/deploy/install-nginx-api-config.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_SOURCE="${SCRIPT_DIR}/nginx/epic-messaging-api.conf"
SITE_NAME="epic-messaging-api"
SITE_AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
SITE_ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"

if [[ ! -f "${CONFIG_SOURCE}" ]]; then
  echo "error: missing ${CONFIG_SOURCE}"
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "error: nginx is not installed or not on PATH"
  exit 1
fi

echo "Installing Nginx API config with edge rate limits"
echo "  source: ${CONFIG_SOURCE}"
echo "  target: ${SITE_AVAILABLE}"

if [[ -f "${SITE_AVAILABLE}" ]]; then
  sudo cp "${SITE_AVAILABLE}" "${SITE_AVAILABLE}.bak.$(date +%Y%m%d%H%M%S)"
fi

sudo cp "${CONFIG_SOURCE}" "${SITE_AVAILABLE}"
sudo ln -sf "${SITE_AVAILABLE}" "${SITE_ENABLED}"
sudo nginx -t
sudo systemctl reload nginx

echo
echo "Nginx config installed and reloaded."
echo "Check active limit_req config with:"
echo "  sudo nginx -T | grep -n \"limit_req\\|server_name\\|proxy_pass\""
