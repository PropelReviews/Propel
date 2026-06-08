#!/usr/bin/env bash
#
# Build the production API image, push it to the environment's ECR repo, and
# trigger a new ECS deployment. Reads identifiers from Terraform outputs so
# there are no hardcoded ARNs.
#
# Usage: scripts/deploy-api.sh <beta|prod>
#   IMAGE_TAG (optional, default: latest)
#
# Requires AWS credentials for the target account (CI: OIDC; local: AWS profile).
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "beta" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <beta|prod>" >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
TAG="${IMAGE_TAG:-latest}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"

ECR_URL="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
CLUSTER="$(terraform -chdir="$TF_DIR" output -raw ecs_cluster_name)"
SERVICE="$(terraform -chdir="$TF_DIR" output -raw ecs_service_name)"
# Optional: the long-running Dagster ingestion service (null when ingestion is
# disabled). `2>/dev/null || true` keeps deploys working before it is provisioned.
INGESTION_SERVICE="$(terraform -chdir="$TF_DIR" output -raw ingestion_service_name 2>/dev/null || true)"
REGISTRY="${ECR_URL%%/*}"

echo "==> Logging in to ECR ($REGISTRY)"
aws ecr get-login-password --region "$REGION" |
  docker login --username AWS --password-stdin "$REGISTRY"

# Build context is the repo root: the image bundles backend/ + orchestration/ so
# the same image serves the API and the Dagster ingestion service.
echo "==> Building $ECR_URL:$TAG"
docker build \
  -f "$REPO_ROOT/infrastructure/docker/backend.prod.Dockerfile" \
  -t "$ECR_URL:$TAG" \
  "$REPO_ROOT"

echo "==> Pushing image"
docker push "$ECR_URL:$TAG"

echo "==> Forcing new ECS deployment ($CLUSTER/$SERVICE)"
aws ecs update-service \
  --cluster "$CLUSTER" \
  --service "$SERVICE" \
  --force-new-deployment \
  --region "$REGION" >/dev/null

# The ingestion service runs the same image; roll it too so it picks up new code.
if [ -n "${INGESTION_SERVICE:-}" ] && [ "$INGESTION_SERVICE" != "null" ]; then
  echo "==> Forcing new ECS deployment ($CLUSTER/$INGESTION_SERVICE)"
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$INGESTION_SERVICE" \
    --force-new-deployment \
    --region "$REGION" >/dev/null
fi

echo "Done. Deployed $ECR_URL:$TAG to $ENV."
