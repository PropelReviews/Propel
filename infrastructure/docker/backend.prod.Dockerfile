# Production image for the FastAPI API and the Dagster ingestion service (shipped
# to ECR -> ECS Fargate). One image serves both: the API service runs uvicorn,
# the ingestion service runs `dagster-service` (daemon + webserver).
#
# Build context is the repo ROOT (the orchestration/ project lives alongside
# backend/):
#   docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api .
#
# Unlike backend.Dockerfile (dev), this bakes the application code into the image
# and runs uvicorn WITHOUT --reload.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# `cron` remains for the legacy opt-in hourly job; `pgrep` (procps) backs the
# Dagster ingestion container health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron procps \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SKIP_UV_SYNC=1

# Dagster (V2 ingestion scheduler) lives in its own venv so the API container's
# frozen app venv stays pristine. Its ops import the `app` package from source
# via PYTHONPATH (set by entrypoint.sh), so this venv needs Dagster PLUS the
# backend's full runtime deps. We co-resolve backend/pyproject.toml (copied to
# /app above) with the Dagster deps so the set can't drift out of sync.
COPY orchestration/pyproject.toml /tmp/orchestration/pyproject.toml
RUN uv venv /opt/orchestration-venv \
    && uv pip install --python /opt/orchestration-venv \
        -r /app/pyproject.toml -r /tmp/orchestration/pyproject.toml

COPY backend/app ./app
# Migrations are applied at container start by the entrypoint, so the image must
# carry the Alembic config and revision scripts.
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
# Bake the Meltano project (taps + target-propel) so ingestion can run
# `meltano run` from this image.
COPY backend/meltano ./meltano
# Dagster orchestration project (definitions, schedule, storage prep).
COPY orchestration ./orchestration

# Meltano is installed as an isolated uv tool (its pinned deps must not collide
# with the app venv); the launcher lands on PATH at /usr/local/bin/meltano. Unlike
# dev, prod has no bind mount, so install the plugins (taps + target-propel) into
# the baked .meltano now rather than at container start.
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "meltano>=3.5,<4" \
    && cd meltano && meltano install

# Entrypoint lives in the backend build context.
COPY backend/entrypoint.sh /entrypoint.sh
# Normalize CRLF (Windows/WSL checkouts) so the shebang is not read as /bin/sh\r
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Legacy hourly ingestion crontab + wrapper (activated by INGESTION_CRON_ENABLED;
# superseded by the Dagster ingestion service but kept as a fallback).
COPY backend/cron/ingestion /etc/cron.d/propel-ingestion
COPY backend/cron/propel-ingestion.sh /usr/local/bin/propel-ingestion
RUN sed -i 's/\r$//' /usr/local/bin/propel-ingestion \
    && chmod 0644 /etc/cron.d/propel-ingestion \
    && chmod +x /usr/local/bin/propel-ingestion

EXPOSE 8000 3000

# ECS has no logConfiguration (no CloudWatch); stdout is not collected.
# Observability is exported to PostHog by the app (OpenTelemetry traces + logs).
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
