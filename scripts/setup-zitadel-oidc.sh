#!/usr/bin/env bash
# Bootstrap a Zitadel OIDC application for the Propel BFF.
#
# Local (default): writes OIDC credentials to .env after docker compose up.
# Cloud: requires ZITADEL_MGMT_TOKEN and a reachable Zitadel issuer — prints
# values to paste into GitHub Environment secrets/variables.
#
# Usage:
#   ./scripts/setup-zitadel-oidc.sh
#   ./scripts/setup-zitadel-oidc.sh --env beta --print-secrets
#   ZITADEL_MGMT_TOKEN=... ./scripts/setup-zitadel-oidc.sh --env prod --print-secrets

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ENV_NAME=""
EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV_NAME="${2:?--env requires beta|prod|local}"
      shift 2
      ;;
    --print-secrets)
      EXTRA+=(--print-secrets)
      shift
      ;;
    --force)
      EXTRA+=(--force)
      shift
      ;;
    -h | --help)
      sed -n '1,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

ARGS=(python3 "$ROOT/scripts/zitadel_bootstrap.py")
if [[ -n "$ENV_NAME" ]]; then
  ARGS+=(--env "$ENV_NAME")
fi
ARGS+=("${EXTRA[@]}")

exec "${ARGS[@]}"
