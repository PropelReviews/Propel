#!/usr/bin/env bash
#
# Shared helpers for the Zitadel cloud scripts (deploy-zitadel.sh,
# reset-zitadel-cloud.sh): Secrets Manager get/put and reading the IAM_OWNER
# PAT that Zitadel's first boot seeds onto EFS.
#
# Source this after exporting REGION:
#   REGION="${AWS_REGION:-us-east-1}"
#   source "$REPO_ROOT/scripts/lib/zitadel-pat.sh"

sm_get() {
  aws secretsmanager get-secret-value \
    --secret-id "$1" --query SecretString --output text --region "$REGION" 2>/dev/null || true
}

sm_put() {
  aws secretsmanager put-secret-value \
    --secret-id "$1" --secret-string "$2" --region "$REGION" >/dev/null
}

# Read the bootstrap admin PAT from /zitadel/bootstrap/admin.pat via ECS Exec on
# the zitadel-login container. Args: <cluster> <service>. Echoes the PAT (or an
# empty string) and returns non-zero when no running task is found.
read_login_pat() {
  local cluster="$1" svc="$2" task raw
  task="$(aws ecs list-tasks --cluster "$cluster" --service-name "$svc" \
    --desired-status RUNNING --query 'taskArns[0]' --output text --region "$REGION" 2>/dev/null || true)"
  [[ -z "$task" || "$task" == "None" ]] && return 1
  raw="$(aws ecs execute-command --cluster "$cluster" --task "$task" --container zitadel-login \
    --interactive --command "cat /zitadel/bootstrap/admin.pat" --region "$REGION" 2>&1 || true)"
  printf '%s' "$raw" |
    grep -v -E 'Session Manager|SessionId|Starting session|Exiting session|installed successfully|execute-command|^$|Cannot perform' |
    tr -d '\r\n' | xargs
}
