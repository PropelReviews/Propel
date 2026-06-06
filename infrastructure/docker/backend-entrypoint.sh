#!/bin/sh
# Sync runtime deps from the bind-mounted lockfile into /opt/venv on every start.
# The venv lives outside /app so mounting ./backend:/app does not hide it.
set -e

export UV_PROJECT_ENVIRONMENT=/opt/venv

if [ -f /app/pyproject.toml ] && [ -f /app/uv.lock ]; then
  uv sync --frozen --no-install-project --no-dev --directory /app
fi

# Apply database migrations before starting the app. Postgres is guaranteed
# healthy via the compose `depends_on` condition. `alembic upgrade head` is a
# no-op when the schema is already current.
if [ -f /app/alembic.ini ]; then
  echo "==> Applying database migrations (alembic upgrade head)"
  alembic -c /app/alembic.ini upgrade head
fi

exec "$@"
