# Production image for the FastAPI API (shipped to ECR -> ECS Fargate).
# Build context is the repository root:
#   docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api .
#
# The same image runs the API (`uvicorn`) or the ingestion service (`ingestion`
# → Dagster daemon + webserver, Meltano workflows in-process).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SKIP_UV_SYNC=1

COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/meltano ./meltano
COPY orchestration /app/orchestration

ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "meltano>=3.5,<4" \
    && cd meltano && meltano install

COPY backend/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

COPY backend/scripts/start-ingestion.sh /app/scripts/start-ingestion.sh
RUN sed -i 's/\r$//' /app/scripts/start-ingestion.sh && chmod +x /app/scripts/start-ingestion.sh

EXPOSE 8000 3000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
