FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Runtime venv outside /app — survives the ./backend:/app bind mount.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY backend/entrypoint.sh /entrypoint.sh
# Normalize CRLF (Windows/WSL checkouts) so the shebang is not read as /bin/sh\r
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Seed the venv at build time so `docker compose up` works before the first bind-mount sync.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
