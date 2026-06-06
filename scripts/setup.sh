#!/usr/bin/env bash
# One-time dev container setup (devcontainer postCreateCommand).
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Installing frontend dependencies (shared volume for frontend container)..."
if [ -f frontend/package.json ]; then
  (cd frontend && npm install)
fi

if [ -f backend/requirements.txt ]; then
  echo "Installing backend dependencies (dev container tooling)..."
  pip install --quiet --no-cache-dir -r backend/requirements.txt \
    || echo "  (backend deps install skipped/failed — non-fatal)"
fi

echo "Setup complete."
