#!/usr/bin/env bash
#
# Break the Zitadel first-boot chicken-and-egg on cloud:
#   * DB was initialized but EFS /zitadel/bootstrap stayed empty → no admin.pat /
#     login-client.pat → Login UI unhealthy → bootstrap cannot run.
#
# Drops the zitadel database, restarts the ECS services so start-from-init re-seeds
# the PAT files, then copies admin.pat into Secrets Manager (MGMT_TOKEN).
#
# Safe only before real users/customers exist (initial prod bootstrap).
#
# Usage: scripts/reset-zitadel-cloud.sh prod
set -euo pipefail

ENV="${1:-}"
if [[ "$ENV" != "prod" ]]; then
  echo "Usage: $0 prod" >&2
  echo "Beta does not host Zitadel; only prod needs this reset." >&2
  exit 1
fi

REGION="${AWS_REGION:-us-east-1}"
CLUSTER="propel-${ENV}"
NAME_PREFIX="propel-${ENV}"
MGMT_SECRET="${NAME_PREFIX}/zitadel/MGMT_TOKEN"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=scripts/lib/zitadel-pat.sh
source "$REPO_ROOT/scripts/lib/zitadel-pat.sh"

aws_cli() {
  aws --region "$REGION" "$@"
}

scale_service() {
  local svc="$1" count="$2"
  echo "==> Scaling $svc → $count"
  aws_cli ecs update-service --cluster "$CLUSTER" --service "$svc" --desired-count "$count" >/dev/null
}

wait_service_steady() {
  local svc="$1" want="$2"
  echo "==> Waiting for $svc to reach $want running task(s)..."
  for _ in $(seq 1 60); do
    local running
    running="$(aws_cli ecs describe-services --cluster "$CLUSTER" --services "$svc" \
      --query 'services[0].runningCount' --output text)"
    if [[ "$running" == "$want" ]]; then
      return 0
    fi
    sleep 10
  done
  echo "ERROR: $svc did not reach $want running tasks in time" >&2
  exit 1
}

drop_zitadel_database() {
  local db_url exec_role subnets sg maint_url
  db_url="$(aws_cli secretsmanager get-secret-value --secret-id "${NAME_PREFIX}/database-url" \
    --query SecretString --output text)"
  exec_role="$(aws_cli ecs describe-task-definition --task-definition "${NAME_PREFIX}-zitadel" \
    --query 'taskDefinition.executionRoleArn' --output text)"
  subnets="$(aws_cli ecs describe-services --cluster "$CLUSTER" --services "${NAME_PREFIX}-zitadel" \
    --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' --output text | tr '\t' ',')"
  sg="$(aws_cli ecs describe-services --cluster "$CLUSTER" --services "${NAME_PREFIX}-zitadel" \
    --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]' --output text)"
  # Connect to the postgres maintenance DB (same master user as DATABASE_URL).
  maint_url="${db_url%/*}/postgres"

  echo "==> Dropping zitadel database (one-off Fargate psql task)"
  local task_arn
  task_arn="$(aws_cli ecs run-task \
    --cluster "$CLUSTER" \
    --launch-type FARGATE \
    --task-definition "$(aws_cli ecs register-task-definition \
      --family "${NAME_PREFIX}-zitadel-db-drop" \
      --requires-compatibilities FARGATE \
      --network-mode awsvpc \
      --cpu 256 --memory 512 \
      --execution-role-arn "$exec_role" \
      --container-definitions "[{\"name\":\"psql\",\"image\":\"postgres:16-alpine\",\"essential\":true,\"command\":[\"psql\",\"$maint_url\",\"-v\",\"ON_ERROR_STOP=1\",\"-c\",\"DROP DATABASE IF EXISTS zitadel WITH (FORCE);\"]}]" \
      --query 'taskDefinition.taskDefinitionArn' --output text)" \
    --network-configuration "awsvpcConfiguration={subnets=[$subnets],securityGroups=[$sg],assignPublicIp=DISABLED}" \
    --query 'tasks[0].taskArn' --output text)"

  echo "==> Waiting for db-drop task $task_arn"
  aws_cli ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$task_arn"
  local exit_code
  exit_code="$(aws_cli ecs describe-tasks --cluster "$CLUSTER" --tasks "$task_arn" \
    --query 'tasks[0].containers[0].exitCode' --output text)"
  if [[ "$exit_code" != "0" ]]; then
    echo "ERROR: db-drop task failed (exit $exit_code)" >&2
    aws_cli ecs describe-tasks --cluster "$CLUSTER" --tasks "$task_arn" \
      --query 'tasks[0].{reason:stoppedReason,containers:containers[*].{name:name,reason:reason,exitCode:exitCode}}' \
      --output json >&2
    exit 1
  fi
}

echo "==> Stopping Zitadel ECS services"
scale_service "${NAME_PREFIX}-zitadel-login" 0
scale_service "${NAME_PREFIX}-zitadel" 0
wait_service_steady "${NAME_PREFIX}-zitadel-login" 0
wait_service_steady "${NAME_PREFIX}-zitadel" 0

drop_zitadel_database

echo "==> Starting Zitadel API (first-boot will seed EFS PAT files)"
scale_service "${NAME_PREFIX}-zitadel" 1
wait_service_steady "${NAME_PREFIX}-zitadel" 1

echo "==> Waiting for /zitadel/bootstrap/admin.pat on EFS..."
PAT=""
for _ in $(seq 1 40); do
  scale_service "${NAME_PREFIX}-zitadel-login" 1
  sleep 20
  PAT="$(read_login_pat "$CLUSTER" "${NAME_PREFIX}-zitadel-login" || true)"
  if [[ -n "$PAT" ]]; then
    break
  fi
done

if [[ -z "$PAT" ]]; then
  cat >&2 <<EOF
ERROR: admin.pat did not appear on EFS after restart.
Check zitadel task logs, then read manually:
  TASK=\$(aws ecs list-tasks --cluster $CLUSTER --service-name ${NAME_PREFIX}-zitadel-login \\
           --desired-status RUNNING --query 'taskArns[0]' --output text)
  aws ecs execute-command --cluster $CLUSTER --task "\$TASK" --container zitadel-login \\
       --interactive --command "cat /zitadel/bootstrap/admin.pat"
EOF
  exit 1
fi

echo "==> Seeding $MGMT_SECRET"
sm_put "$MGMT_SECRET" "$PAT"

scale_service "${NAME_PREFIX}-zitadel-login" 1
wait_service_steady "${NAME_PREFIX}-zitadel-login" 1

echo "Done."
echo "  * Stored IAM_OWNER PAT in $MGMT_SECRET (${#PAT} chars)"
echo "  * Set GitHub environment secret ZITADEL_MGMT_TOKEN to the same value"
echo "  * Re-run Deploy Prod (or: AWS_PROFILE=propel-prod $REPO_ROOT/scripts/deploy-zitadel.sh prod)"
