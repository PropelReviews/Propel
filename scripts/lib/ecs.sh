#!/usr/bin/env bash
# Shared ECS helpers for deploy / rollback scripts.
#
# Requires: aws CLI, jq. Callers set REGION before using these functions.

# Register a new task definition revision from the latest in ``family`` (picks up
# Terraform's newest env/secrets/cpu) with ``image``, then update the service
# once. Avoids a double rollout when CI runs terraform apply then deploy.
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
        | .containerDefinitions |= map(
            .image = $image
            | if (.environment // []) | length > 0 then
                .environment |= map(
                  if .name == "DAGSTER_CURRENT_IMAGE" then .value = $image else . end
                )
              else
                .
              end
          )
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

wait_ecs_services_stable() {
  local cluster=$1
  shift
  local services=("$@")

  echo "==> Waiting for ECS services to stabilize (${services[*]})"
  aws ecs wait services-stable \
    --cluster "$cluster" \
    --services "${services[@]}" \
    --region "$REGION"
}

ecr_image_exists() {
  local repository_name=$1
  local tag=$2

  aws ecr describe-images \
    --repository-name "$repository_name" \
    --image-ids "imageTag=$tag" \
    --region "$REGION" \
    --query 'imageDetails[0].imageDigest' \
    --output text >/dev/null 2>&1
}
