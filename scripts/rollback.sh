#!/usr/bin/env bash
#
# Roll production (or beta) back to a previously deployed git SHA.
#
# Restores:
#   - ECS API / ingestion / Dask services → ECR image tagged with that SHA
#   - Frontend + landing S3 live sites → s3://$bucket/releases/$SHA/
#
# Does NOT run terraform apply. Infra/config stays as-is; only app artifacts
# move. Prefer expand/contract migrations so rolling back code stays safe.
#
# Usage:
#   scripts/rollback.sh <beta|prod> <git-sha>
#   scripts/rollback.sh prod --previous   # SSM previous release (metric target)
#   scripts/rollback.sh prod --list       # show recent ECR release tags
#
# Requires AWS credentials for the target account (CI: OIDC; local: AWS profile).
# Terraform state must be readable (outputs) — run from a checkout that can
# ``terraform init`` the env, or reuse an already-initialized TF_DIR.
set -euo pipefail

ENV="${1:-}"
TARGET="${2:-}"

if [[ "$ENV" != "beta" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <beta|prod> <git-sha|--previous|--list>" >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/ecs.sh
source "$REPO_ROOT/scripts/lib/ecs.sh"
# shellcheck source=lib/release-ssm.sh
source "$REPO_ROOT/scripts/lib/release-ssm.sh"

TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"

if [[ ! -d "$TF_DIR/.terraform" ]]; then
  echo "==> Initializing Terraform in $TF_DIR"
  terraform -chdir="$TF_DIR" init -input=false >/dev/null
fi

ECR_URL="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
CLUSTER="$(terraform -chdir="$TF_DIR" output -raw ecs_cluster_name)"
SERVICE="$(terraform -chdir="$TF_DIR" output -raw ecs_service_name)"
INGESTION_SERVICE="$(terraform -chdir="$TF_DIR" output -raw ingestion_service_name 2>/dev/null || true)"
DASK_WORKER_SERVICE="$(terraform -chdir="$TF_DIR" output -raw dask_worker_service_name 2>/dev/null || true)"
FRONTEND_BUCKET="$(terraform -chdir="$TF_DIR" output -raw frontend_bucket)"
FRONTEND_DIST="$(terraform -chdir="$TF_DIR" output -raw cloudfront_distribution_id)"
LANDING_BUCKET="$(terraform -chdir="$TF_DIR" output -raw landing_bucket)"
LANDING_DIST="$(terraform -chdir="$TF_DIR" output -raw landing_cloudfront_distribution_id)"
API_URL="$(terraform -chdir="$TF_DIR" output -raw api_url)"
REPO_NAME="${ECR_URL##*/}"

if [[ "$TARGET" == "--list" ]]; then
  echo "==> Recent ECR image tags in $REPO_NAME (newest first)"
  aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --region "$REGION" \
    --query 'reverse(sort_by(imageDetails,& imagePushedAt))[:20].imageTags[]' \
    --output text | tr '\t' '\n' | grep -E '^[0-9a-f]{7,40}$' | head -20
  exit 0
fi

if [[ "$TARGET" == "--previous" ]]; then
  TARGET="$(read_previous_release_sha)"
  if [[ -z "$TARGET" || "$TARGET" == "none" ]]; then
    echo "error: no previous release SHA recorded in SSM" >&2
    exit 1
  fi
  echo "==> Using previous release from SSM: $TARGET"
fi

if [[ -z "$TARGET" ]]; then
  echo "Usage: $0 <beta|prod> <git-sha|--previous|--list>" >&2
  exit 1
fi

SHA="$TARGET"
IMAGE="${ECR_URL}:${SHA}"

echo "==> Verifying ECR image $IMAGE"
if ! ecr_image_exists "$REPO_NAME" "$SHA"; then
  echo "error: no ECR image tagged '$SHA' in $REPO_NAME" >&2
  echo "hint: $0 $ENV --list" >&2
  exit 1
fi

s3_release_exists() {
  local bucket=$1
  local sha=$2
  aws s3api head_object \
    --bucket "$bucket" \
    --key "releases/$sha/index.html" \
    --region "$REGION" >/dev/null 2>&1
}

restore_s3_release() {
  local label=$1
  local bucket=$2
  local dist_id=$3
  local sha=$4

  if ! s3_release_exists "$bucket" "$sha"; then
    echo "error: missing s3://$bucket/releases/$sha/index.html" >&2
    echo "hint: that SHA was deployed before release archives existed; redeploy that commit instead" >&2
    exit 1
  fi

  echo "==> Restoring $label from s3://$bucket/releases/$sha/"
  aws s3 sync "s3://$bucket/releases/$sha/" "s3://$bucket/" \
    --delete \
    --exclude "releases/*" \
    --region "$REGION"

  echo "==> Invalidating CloudFront ($dist_id)"
  aws cloudfront create-invalidation \
    --distribution-id "$dist_id" \
    --paths "/*" \
    --region "$REGION" >/dev/null
}

SERVICES=("$SERVICE")

echo "==> Rolling API service ($CLUSTER/$SERVICE) → $IMAGE"
roll_ecs_service_to_image "$CLUSTER" "$SERVICE" "$SERVICE" "$IMAGE" >/dev/null

if [ -n "${INGESTION_SERVICE:-}" ] && [ "$INGESTION_SERVICE" != "null" ]; then
  echo "==> Rolling ingestion service ($CLUSTER/$INGESTION_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$INGESTION_SERVICE" "$INGESTION_SERVICE" "$IMAGE" >/dev/null
  SERVICES+=("$INGESTION_SERVICE")
fi

if [ -n "${DASK_WORKER_SERVICE:-}" ] && [ "$DASK_WORKER_SERVICE" != "null" ]; then
  echo "==> Rolling Dask worker service ($CLUSTER/$DASK_WORKER_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$DASK_WORKER_SERVICE" "$DASK_WORKER_SERVICE" "$IMAGE" >/dev/null
  SERVICES+=("$DASK_WORKER_SERVICE")
fi

restore_s3_release "frontend" "$FRONTEND_BUCKET" "$FRONTEND_DIST" "$SHA"
restore_s3_release "landing" "$LANDING_BUCKET" "$LANDING_DIST" "$SHA"

wait_ecs_services_stable "$CLUSTER" "${SERVICES[@]}"
record_release_sha "$SHA"

echo "==> Smoke check $API_URL/health"
curl -fsS --retry 5 --retry-delay 2 "$API_URL/health" >/dev/null

echo "Done. Rolled $ENV back to $SHA."
