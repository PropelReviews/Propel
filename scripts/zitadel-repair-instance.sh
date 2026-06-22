#!/usr/bin/env bash
#
# Repair the shared Zitadel instance config WITHOUT touching the database.
#
# Re-runs the bootstrap in --strict mode against the live prod instance, which
# re-applies the login policy + Actions V2 mapping hook + login branding, and
# (re)provisions the IAM_OWNER super-admin. Identity providers (e.g. GitHub) are
# defined manually in the Zitadel console and are NOT touched. Unlike
# scripts/reset-zitadel-cloud.sh this NEVER drops the zitadel database, so
# existing orgs, users, and the OIDC app are preserved.
#
# Use this whenever instance-level auth config (login policy, Actions V2 hook,
# branding, super-admin) needs to be re-provisioned out of band, without a full
# code deploy. To fix duplicate/broken GitHub IdPs, edit them in the console.
#
# Usage: scripts/zitadel-repair-instance.sh prod
#
# Requires AWS credentials for the prod account (to read the IAM_OWNER PAT and the
# OIDC client creds from Secrets Manager) or a ZITADEL_MGMT_TOKEN in the
# environment. Set ZITADEL_ADMIN_EMAIL / ZITADEL_ADMIN_PASSWORD to (re)provision
# the console admin.
set -euo pipefail

ENV="${1:-prod}"
if [[ "$ENV" != "prod" ]]; then
  echo "Usage: $0 prod" >&2
  echo "Only prod hosts the shared Zitadel instance; beta has no instance config." >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
NAME_PREFIX="propel-${ENV}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MGMT_SECRET="${NAME_PREFIX}/zitadel/MGMT_TOKEN"
CLIENT_ID_SECRET="${NAME_PREFIX}/app/ZITADEL_CLIENT_ID"
CLIENT_SECRET_SECRET="${NAME_PREFIX}/app/ZITADEL_CLIENT_SECRET"

# shellcheck source=scripts/lib/zitadel-pat.sh
source "$REPO_ROOT/scripts/lib/zitadel-pat.sh"

# ---- Resolve the IAM_OWNER PAT -----------------------------------------------
TOKEN="${ZITADEL_MGMT_TOKEN:-}"
if [[ -z "$TOKEN" ]]; then
  echo "==> Reading Zitadel mgmt PAT from Secrets Manager ($MGMT_SECRET)"
  TOKEN="$(sm_get "$MGMT_SECRET")"
fi
if [[ -z "$TOKEN" || ${#TOKEN} -lt 20 || "$TOKEN" == "pending-sync" || "$TOKEN" == "None" ]]; then
  cat >&2 <<EOF
ERROR: no valid Zitadel IAM_OWNER PAT for $ENV.
Set the ZITADEL_MGMT_TOKEN environment variable, or seed it in Secrets Manager:
  aws secretsmanager put-secret-value --secret-id $MGMT_SECRET --secret-string 'YOUR_PAT_HERE'
EOF
  exit 1
fi

# ---- Reuse the existing OIDC app creds so the repair never rotates the secret -
# Zitadel does not return existing client secrets, so pass the stored values
# through; the bootstrap then reuses the app instead of regenerating its secret
# (which would otherwise require an API redeploy).
_sm_client_id="$(sm_get "$CLIENT_ID_SECRET")"
_sm_client_secret="$(sm_get "$CLIENT_SECRET_SECRET")"
if [[ -n "$_sm_client_id" && "$_sm_client_id" != "pending-bootstrap" && "$_sm_client_id" != "None" ]]; then
  : "${ZITADEL_CLIENT_ID:=$_sm_client_id}"
fi
if [[ -n "$_sm_client_secret" && "$_sm_client_secret" != "pending-bootstrap" && "$_sm_client_secret" != "None" ]]; then
  : "${ZITADEL_CLIENT_SECRET:=$_sm_client_secret}"
fi

echo "==> Repairing Zitadel instance config for $ENV (no database changes)"
ZITADEL_MGMT_TOKEN="$TOKEN" \
  ZITADEL_CLIENT_ID="${ZITADEL_CLIENT_ID:-}" \
  ZITADEL_CLIENT_SECRET="${ZITADEL_CLIENT_SECRET:-}" \
  ZITADEL_ADMIN_EMAIL="${ZITADEL_ADMIN_EMAIL:-}" \
  ZITADEL_ADMIN_PASSWORD="${ZITADEL_ADMIN_PASSWORD:-}" \
  python3 "$REPO_ROOT/scripts/zitadel_bootstrap.py" --env "$ENV" --strict

echo "Done."
echo "  * Verify the hosted Login UI shows a single GitHub button (console-managed)"
echo "  * Verify console login works at https://auth.propel.ninja/ui/console"
echo "  * If the Actions V2 signing key was rotated, also run:"
echo "      scripts/deploy-zitadel.sh prod && scripts/deploy-api.sh prod"
