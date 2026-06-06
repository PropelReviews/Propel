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

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SKIP_UV_SYNC=1

COPY app ./app
# Migrations are applied at container start by the entrypoint, so the image
# must carry the Alembic config and revision scripts.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Entrypoint lives in the backend build context (this image builds from backend/).
COPY entrypoint.sh /entrypoint.sh
# Normalize CRLF (Windows/WSL checkouts) so the shebang is not read as /bin/sh\r
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

# ECS has no logConfiguration (no CloudWatch); stdout is not collected.
# Observability is exported to PostHog by the app (OpenTelemetry traces).
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
