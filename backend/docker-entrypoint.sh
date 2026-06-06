#!/bin/sh
# Production entrypoint: apply database migrations, then start the app.
#
# `alembic upgrade head` is idempotent (a no-op when the schema is already
# current), so it is safe to run on every task start. During a rolling ECS
# deploy the new task migrates the shared database before the load balancer
# routes traffic to it; the old task keeps serving the previous schema until
# it is drained (standard expand/contract migration discipline applies).
set -e

echo "==> Applying database migrations (alembic upgrade head)"
alembic -c /app/alembic.ini upgrade head

exec "$@"
