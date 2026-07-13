#!/usr/bin/env bash
#
# Build the production API image, push it to the environment's ECR repo, and
# trigger a new ECS deployment. Reads identifiers from Terraform outputs so
# there are no hardcoded ARNs.
#
# Usage: scripts/deploy-api.sh <beta|prod>
#   IMAGE_TAG / RELEASE_SHA / GITHUB_SHA — immutable tag to push and roll to
#     (default: git HEAD). Also tagged as ``latest`` for convenience.
#
# Requires AWS credentials for the target account (CI: OIDC; local: AWS profile).
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "beta" && "$ENV" != "prod" ]]; then
  echo "Usage: $0 <beta|prod>" >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/ecs.sh
source "$REPO_ROOT/scripts/lib/ecs.sh"
# shellcheck source=lib/release-sha.sh
source "$REPO_ROOT/scripts/lib/release-sha.sh"

TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"
TAG="$(resolve_release_sha)"

ECR_URL="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
CLUSTER="$(terraform -chdir="$TF_DIR" output -raw ecs_cluster_name)"
SERVICE="$(terraform -chdir="$TF_DIR" output -raw ecs_service_name)"
# Optional: the long-running Dagster ingestion service (null when ingestion is
# disabled). `2>/dev/null || true` keeps deploys working before it is provisioned.
INGESTION_SERVICE="$(terraform -chdir="$TF_DIR" output -raw ingestion_service_name 2>/dev/null || true)"
DASK_WORKER_SERVICE="$(terraform -chdir="$TF_DIR" output -raw dask_worker_service_name 2>/dev/null || true)"
REGISTRY="${ECR_URL%%/*}"
IMAGE="${ECR_URL}:${TAG}"
LATEST_IMAGE="${ECR_URL}:latest"

echo "==> Logging in to ECR ($REGISTRY)"
aws ecr get-login-password --region "$REGION" |
  docker login --username AWS --password-stdin "$REGISTRY"

# Build context is the repo root: the image bundles backend/ + orchestration/ so
# the same image serves the API and the Dagster ingestion service.
echo "==> Building $IMAGE"
docker build \
  -f "$REPO_ROOT/infrastructure/docker/backend.prod.Dockerfile" \
  -t "$IMAGE" \
  -t "$LATEST_IMAGE" \
  "$REPO_ROOT"

echo "==> Pushing image tags ($TAG, latest)"
docker push "$IMAGE"
docker push "$LATEST_IMAGE"

SERVICES=("$SERVICE")

# API: one rollout (new revision + immutable image). Terraform owns the task def
# template but ignores service.task_definition so apply does not deploy.
echo "==> Rolling API service ($CLUSTER/$SERVICE) → $IMAGE"
roll_ecs_service_to_image "$CLUSTER" "$SERVICE" "$SERVICE" "$IMAGE" >/dev/null

# Ingestion: one rollout (new revision + image).
if [ -n "${INGESTION_SERVICE:-}" ] && [ "$INGESTION_SERVICE" != "null" ]; then
  echo "==> Rolling ingestion service ($CLUSTER/$INGESTION_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$INGESTION_SERVICE" "$INGESTION_SERVICE" "$IMAGE" >/dev/null
  SERVICES+=("$INGESTION_SERVICE")
fi

# Dask workers run the same image. Usually scaled to 0 (the Dagster coordinator
# owns desired_count), in which case updating the task def is enough and the
# next scale-up boots tasks on the new image; if workers are mid-run they roll.
if [ -n "${DASK_WORKER_SERVICE:-}" ] && [ "$DASK_WORKER_SERVICE" != "null" ]; then
  echo "==> Rolling Dask worker service ($CLUSTER/$DASK_WORKER_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$DASK_WORKER_SERVICE" "$DASK_WORKER_SERVICE" "$IMAGE" >/dev/null
  SERVICES+=("$DASK_WORKER_SERVICE")
fi

wait_ecs_services_stable "$CLUSTER" "${SERVICES[@]}"

# shellcheck source=lib/release-ssm.sh
source "$REPO_ROOT/scripts/lib/release-ssm.sh"
record_release_sha "$TAG"

echo "Done. Deployed $IMAGE to $ENV."
