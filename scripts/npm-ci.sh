#!/usr/bin/env bash
#
# Run npm ci with retries for transient registry/network failures (common in CI).
#
# Usage: scripts/npm-ci.sh <directory>
#   NPM_CI_MAX_ATTEMPTS  Max tries (default: 4).
#
set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" || ! -f "$DIR/package-lock.json" ]]; then
  echo "Usage: $0 <directory-with-package-lock.json>" >&2
  exit 1
fi

MAX_ATTEMPTS="${NPM_CI_MAX_ATTEMPTS:-4}"
ATTEMPT=1

# Extra resilience for flaky connections to the npm registry.
npm config set fetch-retries 5
npm config set fetch-retry-mintimeout 20000
npm config set fetch-retry-maxtimeout 120000

while (( ATTEMPT <= MAX_ATTEMPTS )); do
  echo "==> npm ci in $DIR (attempt $ATTEMPT/$MAX_ATTEMPTS)"
  if npm --prefix "$DIR" ci; then
    exit 0
  fi

  if (( ATTEMPT == MAX_ATTEMPTS )); then
    echo "npm ci failed after $MAX_ATTEMPTS attempts" >&2
    exit 1
  fi

  DELAY=$(( 5 * ATTEMPT * ATTEMPT ))
  echo "npm ci failed; retrying in ${DELAY}s..." >&2
  sleep "$DELAY"
  ATTEMPT=$(( ATTEMPT + 1 ))
done
