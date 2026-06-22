#!/usr/bin/env bash
# Reconcile Terraform state after reverting main past the Zitadel/PostHog infra apply.
#
# Symptoms on `terraform apply`:
#   * ResourceExistsException creating propel-<env>/app/JWT_SECRET
#   * InvalidParameterValue modifying propel-<env>-db subnet group (subnet in use)
#   * DBParameterGroupAlreadyExists for propel-<env>-aurora-posthog
#   * posthog-warehouse secret already exists or is scheduled for deletion
#
# Fixes JWT + PostHog warehouse state drift after reverting past the Zitadel apply.
#
# Usage:
#   aws sso login --sso-session propel
#   export AWS_PROFILE=propel-beta   # or propel-prod
#   ./scripts/terraform-recover-after-zitadel-revert.sh beta
#
# Then re-run deploy or `terraform apply` in infrastructure/terraform/environments/<env>.

set -euo pipefail

ENV="${1:?usage: $0 <beta|prod>}"
if [[ "$ENV" != "beta" && "$ENV" != "prod" ]]; then
  echo "environment must be beta or prod" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"
PREFIX="propel-$ENV"
JWT_SECRET_ID="${PREFIX}/app/JWT_SECRET"
SESSION_SECRET_ID="${PREFIX}/app/SESSION_SECRET"
POSTHOG_SECRET_ID="${PREFIX}/posthog-warehouse"
POSTHOG_PARAM_GROUP="${PREFIX}-aurora-posthog"

cd "$TF_DIR"
terraform init -input=false

state_has() {
  terraform state list 2>/dev/null | grep -qF "$1"
}

state_rm_if_present() {
  local addr="$1"
  if state_has "$addr"; then
    echo "==> Removing stale state address: $addr"
    terraform state rm "$addr"
  fi
}

echo "==> Clearing Zitadel-era session_secret addresses from state (AWS objects kept)"
state_rm_if_present "module.stack.module.api.aws_secretsmanager_secret_version.session_secret"
state_rm_if_present "module.stack.module.api.aws_secretsmanager_secret.session_secret"
state_rm_if_present "module.stack.module.api.random_password.session_secret"

if state_has "module.stack.module.api.aws_secretsmanager_secret.jwt_secret"; then
  echo "==> jwt_secret already in state — nothing to import"
else
  if aws secretsmanager describe-secret --secret-id "$JWT_SECRET_ID" >/dev/null 2>&1; then
    echo "==> Importing existing JWT secret: $JWT_SECRET_ID"
    terraform import 'module.stack.module.api.aws_secretsmanager_secret.jwt_secret' "$JWT_SECRET_ID"

    version_id="$(
      aws secretsmanager describe-secret --secret-id "$JWT_SECRET_ID" \
        --query 'VersionIdsToStages' --output json \
        | jq -r 'to_entries[] | select(.value[]? == "AWSCURRENT") | .key' \
        | head -1
    )"
    if [[ -z "$version_id" ]]; then
      echo "Could not resolve AWSCURRENT version for $JWT_SECRET_ID" >&2
      exit 1
    fi
    terraform import \
      'module.stack.module.api.aws_secretsmanager_secret_version.jwt_secret' \
      "${JWT_SECRET_ID}|${version_id}"

    if ! state_has "module.stack.module.api.random_password.jwt_secret"; then
      echo "==> Importing random_password.jwt_secret placeholder (value ignored via lifecycle)"
      terraform import 'module.stack.module.api.random_password.jwt_secret' none
    fi
  elif aws secretsmanager describe-secret --secret-id "$SESSION_SECRET_ID" >/dev/null 2>&1; then
    echo "==> JWT_SECRET missing but SESSION_SECRET exists — copying value, then importing JWT"
    session_value="$(aws secretsmanager get-secret-value --secret-id "$SESSION_SECRET_ID" --query SecretString --output text)"
    aws secretsmanager create-secret \
      --name "$JWT_SECRET_ID" \
      --description "JWT signing secret for the ${PREFIX} API (restored after Zitadel revert)." \
      --secret-string "$session_value" \
      --tags Key=Project,Value=propel Key=Environment,Value="$ENV" Key=ManagedBy,Value=terraform
    terraform import 'module.stack.module.api.aws_secretsmanager_secret.jwt_secret' "$JWT_SECRET_ID"
    version_id="$(aws secretsmanager describe-secret --secret-id "$JWT_SECRET_ID" --query 'VersionIdsToStages' --output json | jq -r 'keys[0]')"
    terraform import \
      'module.stack.module.api.aws_secretsmanager_secret_version.jwt_secret' \
      "${JWT_SECRET_ID}|${version_id}"
    terraform import 'module.stack.module.api.random_password.jwt_secret' none
    echo "==> Optional cleanup: delete unused $SESSION_SECRET_ID once deploy succeeds"
  else
    echo "Neither $JWT_SECRET_ID nor $SESSION_SECRET_ID exists — next apply will create JWT_SECRET" >&2
  fi
fi

echo "==> PostHog warehouse parameter group + secret (from prior PostHog apply)"
if aws rds describe-db-cluster-parameter-groups \
  --db-cluster-parameter-group-name "$POSTHOG_PARAM_GROUP" >/dev/null 2>&1; then
  if ! state_has "module.stack.module.database.aws_rds_cluster_parameter_group.posthog[0]"; then
    echo "==> Importing RDS cluster parameter group: $POSTHOG_PARAM_GROUP"
    terraform import \
      'module.stack.module.database.aws_rds_cluster_parameter_group.posthog[0]' \
      "$POSTHOG_PARAM_GROUP"
  fi
fi

posthog_secret_status="$(
  aws secretsmanager describe-secret --secret-id "$POSTHOG_SECRET_ID" \
    --query '{DeletedDate:DeletedDate,VersionIds:VersionIdsToStages}' --output json 2>/dev/null || true
)"
if [[ -n "$posthog_secret_status" && "$posthog_secret_status" != "null" ]]; then
  if jq -e '.DeletedDate != null' <<<"$posthog_secret_status" >/dev/null 2>&1; then
    echo "==> Restoring posthog-warehouse secret (was scheduled for deletion)"
    aws secretsmanager restore-secret --secret-id "$POSTHOG_SECRET_ID" >/dev/null
  fi
  if ! state_has "module.stack.module.database.aws_secretsmanager_secret.posthog_warehouse[0]"; then
    echo "==> Importing posthog-warehouse secret: $POSTHOG_SECRET_ID"
    terraform import \
      'module.stack.module.database.aws_secretsmanager_secret.posthog_warehouse[0]' \
      "$POSTHOG_SECRET_ID"
    posthog_version_id="$(jq -r 'to_entries[] | select(.value[]? == "AWSCURRENT") | .key' <<<"$(aws secretsmanager describe-secret --secret-id "$POSTHOG_SECRET_ID" --query VersionIdsToStages --output json)" | head -1)"
    if [[ -n "$posthog_version_id" ]]; then
      terraform import \
        'module.stack.module.database.aws_secretsmanager_secret_version.posthog_warehouse[0]' \
        "${POSTHOG_SECRET_ID}|${posthog_version_id}"
    fi
    if ! state_has "module.stack.module.database.random_password.posthog_warehouse[0]"; then
      terraform import 'module.stack.module.database.random_password.posthog_warehouse[0]' none
    fi
  fi
fi

echo "==> Plan (expect no jwt_secret / posthog creates):"
terraform plan -input=false

echo ""
echo "Recovery complete. Re-run deploy or apply when the plan looks clean."
