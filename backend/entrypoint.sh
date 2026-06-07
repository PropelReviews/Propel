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
# actually run ingestion — the dedicated cron service, or an API task with cron
# enabled. Plain API containers stay fast, and (together with the per-service
# .meltano volume in docker-compose) this stops two containers from racing on one
# SQLite systemdb, which fails with "database is locked". In dev the project lives
# on the ./backend bind mount, so .meltano can't be baked into the image; it sits
# on its own volume and installs on first start. Prod bakes plugins at build time,
# so the marker dir already exists and this is skipped.
if { [ "$1" = "cron" ] || [ "${INGESTION_CRON_ENABLED:-0}" = "1" ]; } \
  && command -v meltano >/dev/null 2>&1 && [ -f /app/meltano/meltano.yml ]; then
  if [ ! -d /app/meltano/.meltano/extractors ]; then
    echo "==> Installing Meltano plugins (first run; this can take a few minutes)"
    (cd /app/meltano && meltano install) \
      || echo "WARN: 'meltano install' failed; ingestion runs will fail until it succeeds"
  fi
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
