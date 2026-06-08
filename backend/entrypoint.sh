#!/bin/sh
set -e

# Dev images sync deps from the bind-mounted lockfile on every start. Production
# sets SKIP_UV_SYNC=1 because dependencies are baked in at build time.
if [ "${SKIP_UV_SYNC:-0}" != "1" ] && [ -f /app/pyproject.toml ] && [ -f /app/uv.lock ]; then
  export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-/opt/venv}"
  uv sync --frozen --no-install-project --no-dev --directory /app
fi

# Deploys (the API service) own schema migrations. SKIP_MIGRATIONS=1 lets the
# scheduled ingestion task run without touching the schema, so an hourly run can
# never race an in-flight migration.
if [ "${SKIP_MIGRATIONS:-0}" != "1" ] && [ -f /app/alembic.ini ]; then
  echo "==> Applying database migrations (alembic upgrade head)"
  alembic -c /app/alembic.ini upgrade head
fi

# Materialize Meltano plugins (taps + target-propel), but only in containers that
# actually run ingestion — the Dagster service (dev `dagster` / prod
# `dagster-service`), the dedicated cron service, or an API task with cron
# enabled. Plain API containers stay fast, and (together with the per-service
# .meltano volume in docker-compose) this stops two containers from racing on one
# SQLite systemdb, which fails with "database is locked". In dev the project lives
# on the ./backend bind mount, so .meltano can't be baked into the image; it sits
# on its own volume and installs on first start. Prod bakes plugins at build time,
# so the marker dir already exists and this is skipped.
if { [ "$1" = "cron" ] || [ "$1" = "dagster" ] || [ "$1" = "dagster-service" ] \
  || [ "${INGESTION_CRON_ENABLED:-0}" = "1" ]; } \
  && command -v meltano >/dev/null 2>&1 && [ -f /app/meltano/meltano.yml ]; then
  if [ ! -d /app/meltano/.meltano/extractors ]; then
    echo "==> Installing Meltano plugins (first run; this can take a few minutes)"
    (cd /app/meltano && meltano install) \
      || echo "WARN: 'meltano install' failed; ingestion runs will fail until it succeeds"
  fi
fi

# Local dev runs the combined `dagster dev` (webserver + daemon) directly as the
# container command. Persist run/event/schedule history in our Postgres (the
# dedicated `dagster` schema, which lives in the pgdata volume) so it survives
# container resets / `docker compose down` — the same storage prod uses. Without
# this, `dagster dev` defaults to ephemeral SQLite under DAGSTER_HOME and history
# is lost whenever the container is recreated. Falls back to SQLite if the DB
# prep fails (e.g. Postgres not reachable yet).
if [ "$1" = "dagster" ]; then
  : "${DAGSTER_HOME:=/tmp/dagster}"
  export DAGSTER_HOME
  mkdir -p "$DAGSTER_HOME"

  # The orchestration project is bind-mounted at /orchestration in dev; fall back
  # to the baked /app/orchestration path just in case.
  ORCH_DIR=/orchestration
  [ -d "$ORCH_DIR" ] || ORCH_DIR=/app/orchestration

  if DAGSTER_PG_URL="$(python "$ORCH_DIR/scripts/prepare_dagster_db.py")" \
    && [ -n "$DAGSTER_PG_URL" ]; then
    export DAGSTER_PG_URL
    cp "$ORCH_DIR/dagster.yaml" "$DAGSTER_HOME/dagster.yaml"
    echo "==> Dagster storage: Postgres ('dagster' schema) — run history persists across restarts"
    dagster instance migrate || echo "WARN: 'dagster instance migrate' failed"
  else
    echo "WARN: Dagster DB prep failed; using ephemeral SQLite in $DAGSTER_HOME (run history will NOT persist)"
  fi
fi

# Dagster ingestion service (V2 scheduler): a long-running daemon (owns the
# hourly schedule -> orchestrator.run_all) plus the webserver (UI on
# DAGSTER_PORT). Dagster's own run/event/schedule storage shares the app's
# Postgres but lives in a dedicated `dagster` schema so its alembic_version never
# collides with the app's migrations (see orchestration/scripts/prepare_dagster_db.py).
if [ "$1" = "dagster-service" ]; then
  echo "==> Starting Dagster ingestion service (daemon + webserver)"
  : "${DAGSTER_HOME:=/tmp/dagster}"
  export DAGSTER_HOME
  mkdir -p "$DAGSTER_HOME"
  cp /app/orchestration/dagster.yaml "$DAGSTER_HOME/dagster.yaml"

  # Run Dagster from its own venv (keeps the API venv pristine); import the
  # backend `app` and `propel_orchestration` packages from source. `meltano`
  # stays resolvable on PATH (isolated uv tool in /usr/local/bin).
  export PATH="/opt/orchestration-venv/bin:$PATH"
  export PYTHONPATH="/app:/app/orchestration${PYTHONPATH:+:$PYTHONPATH}"

  DAGSTER_PG_URL="$(python /app/orchestration/scripts/prepare_dagster_db.py)"
  export DAGSTER_PG_URL

  cd /app/orchestration

  echo "==> Migrating Dagster instance storage"
  dagster instance migrate || echo "WARN: 'dagster instance migrate' failed"

  # Daemon in the background, webserver in the foreground (PID 1). The container
  # health check watches the daemon; the ALB health check watches the webserver.
  dagster-daemon run &
  exec dagster-webserver -h 0.0.0.0 -p "${DAGSTER_PORT:-3000}" -w /app/orchestration/workspace.yaml
fi

# On-server cron (V1 ingestion scheduler). cron jobs start with an empty
# environment, so snapshot the current one (including PATH for the venv) into a
# file the wrapper sources. shlex.quote keeps values with spaces/quotes safe.
snapshot_env_for_cron() {
  python -c 'import os, shlex; print("\n".join(f"export {k}={shlex.quote(v)}" for k, v in os.environ.items()))' \
    > /etc/propel-ingestion.env
}

# Dedicated ingestion service: `crond` is the main process (foreground).
if [ "$1" = "cron" ]; then
  echo "==> Starting ingestion cron (foreground, hourly)"
  snapshot_env_for_cron
  exec cron -f
fi

# Same task as the API: start crond in the background, then exec uvicorn.
# Opt-in via INGESTION_CRON_ENABLED=1 so plain dev/API containers are unaffected.
if [ "${INGESTION_CRON_ENABLED:-0}" = "1" ]; then
  echo "==> Starting ingestion cron (background, hourly)"
  snapshot_env_for_cron
  cron
fi

exec "$@"
