#!/bin/sh
set -e

# Dev images sync deps from the bind-mounted lockfile on every start. Production
# sets SKIP_UV_SYNC=1 because dependencies are baked in at build time.
if [ "${SKIP_UV_SYNC:-0}" != "1" ] && [ -f /app/pyproject.toml ] && [ -f /app/uv.lock ]; then
  export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-/opt/venv}"
  uv sync --frozen --no-install-project --no-dev --directory /app
fi

# Deploys (the API service) own schema migrations. SKIP_MIGRATIONS=1 lets the
# ingestion service run without touching the schema.
if [ "${SKIP_MIGRATIONS:-0}" != "1" ] && [ -f /app/alembic.ini ]; then
  echo "==> Applying database migrations (alembic upgrade head)"
  alembic -c /app/alembic.ini upgrade head
fi

# Materialize Meltano plugins in the ingestion service only. Plain API containers
# stay fast; the per-service .meltano volume in docker-compose avoids SQLite
# locking races between containers.
if [ "$1" = "ingestion" ] \
  && command -v meltano >/dev/null 2>&1 && [ -f /app/meltano/meltano.yml ]; then
  if [ ! -d /app/meltano/.meltano/extractors ]; then
    echo "==> Installing Meltano plugins (first run; this can take a few minutes)"
    (cd /app/meltano && meltano install) \
      || echo "WARN: 'meltano install' failed; ingestion runs will fail until it succeeds"
  fi
fi

# Ingestion service: Dagster daemon + webserver; workflows run in-process.
if [ "$1" = "ingestion" ]; then
  echo "==> Starting ingestion service"
  exec sh /app/scripts/start-ingestion.sh
fi

exec "$@"
