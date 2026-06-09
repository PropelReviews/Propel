#!/usr/bin/env bash
#
# Force a new ECS deployment of the API + ingestion (Dagster) services without
# rebuilding or pushing an image. Use after `deploy-api.sh` has already pushed
# the tag you want, or to make services pick up config-only changes.
#
# Usage: scripts/restart-api.sh <beta|prod>
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
TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"

CLUSTER="$(terraform -chdir="$TF_DIR" output -raw ecs_cluster_name)"
SERVICE="$(terraform -chdir="$TF_DIR" output -raw ecs_service_name)"
INGESTION_SERVICE="$(terraform -chdir="$TF_DIR" output -raw ingestion_service_name 2>/dev/null || true)"

SERVICES=("$SERVICE")
if [ -n "${INGESTION_SERVICE:-}" ] && [ "$INGESTION_SERVICE" != "null" ]; then
  SERVICES+=("$INGESTION_SERVICE")
fi

for svc in "${SERVICES[@]}"; do
  echo "==> Forcing new ECS deployment ($CLUSTER/$svc)"
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$svc" \
    --force-new-deployment \
    --region "$REGION" >/dev/null
done

echo "==> Waiting for services to stabilize"
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "${SERVICES[@]}" \
  --region "$REGION"

echo "Done. $ENV services restarted: ${SERVICES[*]}"
