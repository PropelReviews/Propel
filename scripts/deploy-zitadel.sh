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

sm_get() {
  aws secretsmanager get-secret-value \
    --secret-id "$1" --query SecretString --output text --region "$REGION" 2>/dev/null || true
}

sm_put() {
  aws secretsmanager put-secret-value \
    --secret-id "$1" --secret-string "$2" --region "$REGION" >/dev/null
}

# ---- Resolve the IAM_OWNER PAT -----------------------------------------------
TOKEN="${ZITADEL_MGMT_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "==> Reading Zitadel mgmt PAT from Secrets Manager ($MGMT_SECRET)"
  TOKEN="$(sm_get "$MGMT_SECRET")"
fi
if [[ -z "$TOKEN" || "$TOKEN" == "pending-sync" || "$TOKEN" == "None" ]]; then
  cat >&2 <<EOF
ERROR: no Zitadel IAM_OWNER PAT available for $ENV.
Set the ZITADEL_MGMT_TOKEN environment secret, or store it in Secrets Manager:
  aws secretsmanager put-secret-value --secret-id $MGMT_SECRET --secret-string '<PAT>'
For the very first prod bootstrap, retrieve the PAT from the running container
(see docs/deployment/zitadel.md "First-time bootstrap").
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
ZITADEL_MGMT_TOKEN="$TOKEN" \
  python3 "$REPO_ROOT/scripts/zitadel_bootstrap.py" --env "$ENV" --emit-json "$TMP_JSON"

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

echo "Done. $ENV OIDC app provisioned; deploy-api.sh will roll the API onto the new secrets."
