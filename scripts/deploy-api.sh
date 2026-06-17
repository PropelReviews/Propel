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
IMAGE="${ECR_URL}:${TAG}"

# Register a new task definition revision from the latest in ``family`` (picks up
# Terraform's newest env/secrets/cpu) with ``image``, then update the service
# once. Avoids a double rollout when CI runs terraform apply then this script.
roll_ecs_service_to_image() {
  local cluster=$1
  local service=$2
  local family=$3
  local image=$4

  local register_json new_arn
  register_json=$(aws ecs describe-task-definition \
    --task-definition "$family" \
    --region "$REGION" \
    --query 'taskDefinition' \
    --output json \
    | jq --arg image "$image" '
        del(
          .taskDefinitionArn,
          .revision,
          .status,
          .requiresAttributes,
          .compatibilities,
          .registeredAt,
          .registeredBy
        )
        | .containerDefinitions |= map(.image = $image)
      ')

  new_arn=$(aws ecs register-task-definition \
    --region "$REGION" \
    --cli-input-json "$register_json" \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

  aws ecs update-service \
    --cluster "$cluster" \
    --service "$service" \
    --task-definition "$new_arn" \
    --region "$REGION" >/dev/null

  echo "$new_arn"
}

echo "==> Logging in to ECR ($REGISTRY)"
aws ecr get-login-password --region "$REGION" |
  docker login --username AWS --password-stdin "$REGISTRY"

# Build context is the repo root: the image bundles backend/ + orchestration/ so
# the same image serves the API and the Dagster ingestion service.
# GIT_SHA is baked in as PostHog release metadata (mirrors deploy-frontend.sh).
GIT_SHA="${GITHUB_SHA:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
echo "==> Building $IMAGE (git $GIT_SHA)"
docker build \
  -f "$REPO_ROOT/infrastructure/docker/backend.prod.Dockerfile" \
  --build-arg GIT_SHA="$GIT_SHA" \
  -t "$IMAGE" \
  "$REPO_ROOT"

echo "==> Pushing image"
docker push "$IMAGE"

API_FAMILY="${SERVICE}"
echo "==> Rolling API service ($CLUSTER/$SERVICE)"
roll_ecs_service_to_image "$CLUSTER" "$SERVICE" "$API_FAMILY" "$IMAGE"

# Ingestion: one rollout (new revision + image). Terraform owns the task def
# template but ignores service.task_definition so apply does not deploy.
if [ -n "${INGESTION_SERVICE:-}" ] && [ "$INGESTION_SERVICE" != "null" ]; then
  echo "==> Rolling ingestion service ($CLUSTER/$INGESTION_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$INGESTION_SERVICE" "$INGESTION_SERVICE" "$IMAGE"
fi

# Dask workers run the same image. Usually scaled to 0 (the Dagster coordinator
# owns desired_count), in which case force-new-deployment is a no-op and the
# next scale-up boots tasks on the new image; if workers are mid-run they roll.
DASK_WORKER_SERVICE="$(terraform -chdir="$TF_DIR" output -raw dask_worker_service_name 2>/dev/null || true)"
if [ -n "${DASK_WORKER_SERVICE:-}" ] && [ "$DASK_WORKER_SERVICE" != "null" ]; then
  echo "==> Rolling Dask worker service ($CLUSTER/$DASK_WORKER_SERVICE)"
  roll_ecs_service_to_image "$CLUSTER" "$DASK_WORKER_SERVICE" "$DASK_WORKER_SERVICE" "$IMAGE"
fi

echo "Done. Deployed $IMAGE to $ENV."
