FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Runtime venv outside /app — survives the ./backend:/app bind mount.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Meltano is installed as an isolated uv tool so its pinned deps never collide
# with the app venv. Plugins install at container start in the ingestion service.
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "meltano>=3.5,<4"

COPY backend/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

COPY backend/scripts/start-ingestion.sh /app/scripts/start-ingestion.sh
RUN sed -i 's/\r$//' /app/scripts/start-ingestion.sh && chmod +x /app/scripts/start-ingestion.sh

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
