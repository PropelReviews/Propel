FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# cron drives the hourly ingestion job (V1 scheduler).
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

# Runtime venv outside /app — survives the ./backend:/app bind mount.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Meltano (ingestion extraction engine) is installed as an isolated uv tool so
# its pinned deps never collide with the app venv. The launcher lands on PATH at
# /usr/local/bin/meltano; the orchestrator shells out to it via `meltano run`.
# Plugins (taps + target-propel) are installed at container start by entrypoint.sh
# because the Meltano project lives on the ./backend bind mount in dev.
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "meltano>=3.5,<4"

COPY backend/entrypoint.sh /entrypoint.sh
# Normalize CRLF (Windows/WSL checkouts) so the shebang is not read as /bin/sh\r
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Hourly ingestion crontab + wrapper (activated by the ingestion-cron service).
COPY backend/cron/ingestion /etc/cron.d/propel-ingestion
COPY backend/cron/propel-ingestion.sh /usr/local/bin/propel-ingestion
RUN sed -i 's/\r$//' /usr/local/bin/propel-ingestion \
    && chmod 0644 /etc/cron.d/propel-ingestion \
    && chmod +x /usr/local/bin/propel-ingestion

# Seed the venv at build time so `docker compose up` works before the first bind-mount sync.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
