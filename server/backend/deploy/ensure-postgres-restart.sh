#!/usr/bin/env bash
# Ensure the teammate Postgres container restarts after VM reboot.
#
# Run on the VM:
#   bash server/backend/deploy/ensure-postgres-restart.sh [container-name]
#
# Default container name: epic-postgres

set -euo pipefail

CONTAINER_NAME="${1:-epic-postgres}"

if ! docker inspect "${CONTAINER_NAME}" > /dev/null 2>&1; then
  echo "error: container '${CONTAINER_NAME}' not found"
  echo "Running containers:"
  docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
  exit 1
fi

docker update --restart unless-stopped "${CONTAINER_NAME}"

echo "Restart policy set to 'unless-stopped' for ${CONTAINER_NAME}"
docker inspect "${CONTAINER_NAME}" --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}}'
