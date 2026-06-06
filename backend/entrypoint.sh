#!/bin/sh
set -e

# Dev images sync deps from the bind-mounted lockfile on every start. Production
# sets SKIP_UV_SYNC=1 because dependencies are baked in at build time.
if [ "${SKIP_UV_SYNC:-0}" != "1" ] && [ -f /app/pyproject.toml ] && [ -f /app/uv.lock ]; then
  export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-/opt/venv}"
  uv sync --frozen --no-install-project --no-dev --directory /app
fi

if [ -f /app/alembic.ini ]; then
  echo "==> Applying database migrations (alembic upgrade head)"
  alembic -c /app/alembic.ini upgrade head
fi

exec "$@"
