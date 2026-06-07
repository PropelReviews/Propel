#!/bin/sh
# Wrapper invoked by cron (see backend/cron/ingestion). Restores the container
# environment snapshot — which includes PATH pointing at the right venv (/opt/venv
# in dev, /app/.venv in prod) — then runs the ingestion CLI.
set -e

if [ -f /etc/propel-ingestion.env ]; then
  . /etc/propel-ingestion.env
fi

cd /app
echo "==> $(date -u +%Y-%m-%dT%H:%M:%SZ) propel ingestion run"
exec python -m app.ingestion.cli run
