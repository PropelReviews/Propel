#!/usr/bin/env bash
# Cloud agent bootstrap — runs from .cursor/environment.json before each agent
# session (or from a cached snapshot after the first successful run).
#
# Installs the same deps as scripts/setup.sh, but:
# - bootstraps uv when the VM does not have it (cloud agents are not the devcontainer image)
# - treats backend install failure as fatal (setup.sh logs and continues)
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

echo "Installing frontend dependencies..."
(cd frontend && npm install)

echo "Installing backend dependencies..."
(cd backend && uv sync)

echo "Cloud setup complete."
