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

# AWS SSO profiles (propel-beta / propel-prod). Idempotent: never clobber an
# existing ~/.aws/config so personal tweaks survive a rebuild.
AWS_CONFIG="$HOME/.aws/config"
if [ ! -f "$AWS_CONFIG" ]; then
  echo "Installing AWS SSO config -> $AWS_CONFIG"
  mkdir -p "$HOME/.aws"
  cp .devcontainer/aws-config "$AWS_CONFIG"
  echo "  Run 'aws sso login --sso-session propel' to authenticate."
else
  echo "AWS config already exists ($AWS_CONFIG) — leaving it untouched."
fi

echo "Setup complete."
