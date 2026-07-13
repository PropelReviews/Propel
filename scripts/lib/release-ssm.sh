#!/usr/bin/env bash
# Record the live release SHA in SSM so metric-driven rollbacks know the
# previous good version. Call after a successful deploy or rollback.
#
# Usage (after sourcing / setting ENV, REGION, TF_DIR, RELEASE_SHA):
#   record_release_sha "$RELEASE_SHA"

record_release_sha() {
  local sha=$1
  local current_param previous_param current_value

  current_param="$(terraform -chdir="$TF_DIR" output -raw release_current_parameter 2>/dev/null || true)"
  previous_param="$(terraform -chdir="$TF_DIR" output -raw release_previous_parameter 2>/dev/null || true)"

  if [[ -z "$current_param" || "$current_param" == "null" ]]; then
    echo "==> Skipping SSM release tracking (parameters not provisioned yet)"
    return 0
  fi

  current_value="$(aws ssm get-parameter \
    --name "$current_param" \
    --region "$REGION" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "none")"

  if [[ "$current_value" != "$sha" && "$current_value" != "none" && -n "$current_value" ]]; then
    echo "==> Recording previous release $current_value → $previous_param"
    aws ssm put-parameter \
      --name "$previous_param" \
      --value "$current_value" \
      --type String \
      --overwrite \
      --region "$REGION" >/dev/null
  fi

  echo "==> Recording current release $sha → $current_param"
  aws ssm put-parameter \
    --name "$current_param" \
    --value "$sha" \
    --type String \
    --overwrite \
    --region "$REGION" >/dev/null
}

read_previous_release_sha() {
  local previous_param
  previous_param="$(terraform -chdir="$TF_DIR" output -raw release_previous_parameter 2>/dev/null || true)"
  if [[ -z "$previous_param" || "$previous_param" == "null" ]]; then
    echo "error: release_previous_parameter not available" >&2
    return 1
  fi
  aws ssm get-parameter \
    --name "$previous_param" \
    --region "$REGION" \
    --query 'Parameter.Value' \
    --output text
}
