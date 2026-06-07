#!/bin/sh
# Start Dagster (daemon + webserver) for the ingestion service.
set -e

export DAGSTER_HOME="${DAGSTER_HOME:-/app/dagster_home}"
mkdir -p "$DAGSTER_HOME"

INSTANCE_CONFIG="${DAGSTER_INSTANCE_CONFIG:-/app/orchestration/dagster.yaml}"
if [ -f "$INSTANCE_CONFIG" ]; then
  cp "$INSTANCE_CONFIG" "$DAGSTER_HOME/dagster.yaml"
fi

WORKSPACE="${DAGSTER_WORKSPACE:-/app/orchestration/workspace.yaml}"
WEB_HOST="${DAGSTER_WEB_HOST:-0.0.0.0}"
WEB_PORT="${DAGSTER_WEB_PORT:-3000}"

echo "==> Starting ingestion service (Dagster, workspace=$WORKSPACE)"
dagster-daemon run -w "$WORKSPACE" &
exec dagster-webserver -h "$WEB_HOST" -p "$WEB_PORT" -w "$WORKSPACE"
