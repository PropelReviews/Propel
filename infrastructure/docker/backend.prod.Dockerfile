# Production image for the FastAPI API (shipped to ECR -> ECS Fargate).
# Build context is the `backend/` directory:
#   docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api backend
#
# Unlike backend.Dockerfile (dev), this bakes the application code into the
# image and runs uvicorn WITHOUT --reload.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# cron drives the hourly ingestion job (V1 scheduler, opt-in via
# INGESTION_CRON_ENABLED). Inert unless enabled.
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SKIP_UV_SYNC=1

COPY app ./app
# Migrations are applied at container start by the entrypoint, so the image
# must carry the Alembic config and revision scripts.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
# Bake the Meltano project (taps + target-propel) so the ingestion CLI can run
# `meltano run` from this image.
COPY meltano ./meltano

# Meltano is installed as an isolated uv tool (its pinned deps must not collide
# with the app venv); the launcher lands on PATH at /usr/local/bin/meltano. Unlike
# dev, prod has no bind mount, so install the plugins (taps + target-propel) into
# the baked .meltano now rather than at container start.
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "meltano>=3.5,<4" \
    && cd meltano && meltano install

# Entrypoint lives in the backend build context (this image builds from backend/).
COPY entrypoint.sh /entrypoint.sh
# Normalize CRLF (Windows/WSL checkouts) so the shebang is not read as /bin/sh\r
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Hourly ingestion crontab + wrapper (activated by INGESTION_CRON_ENABLED).
COPY cron/ingestion /etc/cron.d/propel-ingestion
COPY cron/propel-ingestion.sh /usr/local/bin/propel-ingestion
RUN sed -i 's/\r$//' /usr/local/bin/propel-ingestion \
    && chmod 0644 /etc/cron.d/propel-ingestion \
    && chmod +x /usr/local/bin/propel-ingestion

EXPOSE 8000

# ECS has no logConfiguration (no CloudWatch); stdout is not collected.
# Observability is exported to PostHog by the app (OpenTelemetry traces).
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
