#!/usr/bin/env bash
#
# Provision this environment's OIDC application + instance config against the
# single shared Zitadel instance (hosted in prod), then publish the resulting
# client id/secret into this environment's Secrets Manager so the API task can
# consume them. Idempotent — safe to run on every deploy, before deploy-api.sh.
#
# Topology (see docs/deployment/zitadel.md):
#   * prod  hosts the instance AND registers the "Propel Prod" project/app, the
#           GitHub IdP, login branding, and the human super-admin.
#   * beta  hosts nothing; it registers the "Propel Beta" project/app on the prod
#           instance using the prod IAM_OWNER PAT, and writes its own client
#           creds into the beta account's Secrets Manager.
#
# Usage: scripts/deploy-zitadel.sh <beta|prod>
#
# Requires AWS credentials for the target account + a Zitadel IAM_OWNER PAT,
# resolved in order:
#   1. $ZITADEL_MGMT_TOKEN  (CI: environment secret)
#   2. Secrets Manager:     <name_prefix>/zitadel/MGMT_TOKEN
#
# First-time only: retrieve the auto-generated admin PAT from the running prod
# container and store it (see docs/deployment/zitadel.md "First-time bootstrap").
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "beta" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <beta|prod>" >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
NAME_PREFIX="propel-${ENV}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MGMT_SECRET="${NAME_PREFIX}/zitadel/MGMT_TOKEN"
CLIENT_ID_SECRET="${NAME_PREFIX}/app/ZITADEL_CLIENT_ID"
CLIENT_SECRET_SECRET="${NAME_PREFIX}/app/ZITADEL_CLIENT_SECRET"
ACTIONS_SIGNING_KEY_SECRET="${NAME_PREFIX}/zitadel/ACTIONS_SIGNING_KEY"

# shellcheck source=scripts/lib/zitadel-pat.sh
source "$REPO_ROOT/scripts/lib/zitadel-pat.sh"

# ---- Resolve the IAM_OWNER PAT -----------------------------------------------
TOKEN="${ZITADEL_MGMT_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "==> Reading Zitadel mgmt PAT from Secrets Manager ($MGMT_SECRET)"
  TOKEN="$(sm_get "$MGMT_SECRET")"
fi
_invalid_pat() {
  [[ -z "$1" || "$1" == "pending-sync" || "$1" == "None" || "$1" == "<PAT>" || ${#1} -lt 20 ]]
}

# Only prod hosts the instance, so EFS first-boot PATs only exist there.
if _invalid_pat "$TOKEN" && [[ "$ENV" == "prod" ]]; then
  echo "==> Trying EFS bootstrap PAT from ${NAME_PREFIX}-zitadel-login (prod first-boot)"
  TOKEN="$(read_login_pat "$NAME_PREFIX" "${NAME_PREFIX}-zitadel-login" || true)"
fi
if _invalid_pat "$TOKEN"; then
  cat >&2 <<EOF
ERROR: no valid Zitadel IAM_OWNER PAT available for $ENV.
Set the ZITADEL_MGMT_TOKEN environment secret, or store it in Secrets Manager:
  aws secretsmanager put-secret-value --secret-id $MGMT_SECRET --secret-string 'YOUR_PAT_HERE'
First-time prod: Zitadel seeds admin.pat on EFS during first boot. If the Login UI
is unhealthy and EFS is empty, reset once (see scripts/reset-zitadel-cloud.sh).
EOF
  exit 1
fi

# ---- Run the (stdlib-only) Python bootstrap ----------------------------------
# The bootstrap waits for the instance to be ready, ensures the per-env project +
# OIDC app (+ instance config when prod), and writes the minted client creds to
# a JSON file we hand off to Secrets Manager below.
TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

echo "==> Bootstrapping Zitadel project/app for $ENV"
# Instance config (GitHub IdP, super-admin) needs the GitHub App OAuth creds on prod.
if [[ "$ENV" == "prod" ]]; then
  : "${GITHUB_APP_CLIENT_SECRET:=$(sm_get "${NAME_PREFIX}/app/GITHUB_APP_CLIENT_SECRET")}"
  # Legacy fallback: older configs only set the standalone OAuth app's client id.
  : "${GITHUB_APP_CLIENT_ID:=${OAUTH_GITHUB_CLIENT_ID:-}}"
fi
# Zitadel does not return existing OIDC client secrets — pass SM values so re-deploys
# reuse credentials when the app already exists (idempotent CI).
_sm_client_id="$(sm_get "$CLIENT_ID_SECRET")"
_sm_client_secret="$(sm_get "$CLIENT_SECRET_SECRET")"
if [[ -n "$_sm_client_id" && "$_sm_client_id" != "pending-bootstrap" && "$_sm_client_id" != "None" ]]; then
  : "${ZITADEL_CLIENT_ID:=$_sm_client_id}"
fi
if [[ -n "$_sm_client_secret" && "$_sm_client_secret" != "pending-bootstrap" && "$_sm_client_secret" != "None" ]]; then
  : "${ZITADEL_CLIENT_SECRET:=$_sm_client_secret}"
fi
# Prod owns the shared instance config, so a broken GitHub IdP / super-admin must
# fail the deploy loudly rather than ship silently — run the bootstrap in --strict.
STRICT_FLAG=()
if [[ "$ENV" == "prod" ]]; then
  STRICT_FLAG=(--strict)
fi
ZITADEL_MGMT_TOKEN="$TOKEN" \
  ZITADEL_CLIENT_ID="${ZITADEL_CLIENT_ID:-}" \
  ZITADEL_CLIENT_SECRET="${ZITADEL_CLIENT_SECRET:-}" \
  GITHUB_APP_CLIENT_ID="${GITHUB_APP_CLIENT_ID:-}" \
  GITHUB_APP_CLIENT_SECRET="${GITHUB_APP_CLIENT_SECRET:-}" \
  ZITADEL_ADMIN_EMAIL="${ZITADEL_ADMIN_EMAIL:-}" \
  ZITADEL_ADMIN_PASSWORD="${ZITADEL_ADMIN_PASSWORD:-}" \
  python3 "$REPO_ROOT/scripts/zitadel_bootstrap.py" --env "$ENV" \
    "${STRICT_FLAG[@]}" --emit-json "$TMP_JSON"

CLIENT_ID="$(jq -r '.client_id' "$TMP_JSON")"
CLIENT_SECRET="$(jq -r '.client_secret' "$TMP_JSON")"
if [[ -z "$CLIENT_ID" || "$CLIENT_ID" == "null" || -z "$CLIENT_SECRET" || "$CLIENT_SECRET" == "null" ]]; then
  echo "ERROR: bootstrap did not emit client credentials" >&2
  exit 1
fi

# ---- Publish into this environment's Secrets Manager -------------------------
echo "==> Publishing OIDC client id/secret to Secrets Manager"
sm_put "$CLIENT_ID_SECRET" "$CLIENT_ID"
sm_put "$CLIENT_SECRET_SECRET" "$CLIENT_SECRET"

ACTIONS_SIGNING_KEY="$(jq -r '.actions_signing_key // empty' "$TMP_JSON")"
if [[ -n "$ACTIONS_SIGNING_KEY" && "$ACTIONS_SIGNING_KEY" != "null" ]]; then
  echo "==> Publishing Zitadel Actions signing key to Secrets Manager"
  sm_put "$ACTIONS_SIGNING_KEY_SECRET" "$ACTIONS_SIGNING_KEY"
fi

echo "Done. $ENV OIDC app provisioned; deploy-api.sh will roll the API onto the new secrets."
