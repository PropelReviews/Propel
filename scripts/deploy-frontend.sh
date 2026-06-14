#!/usr/bin/env bash
#
# Build the Vite SPA for an environment, sync it to the S3 bucket, and
# invalidate CloudFront. Reads identifiers from Terraform outputs.
#
# Usage: scripts/deploy-frontend.sh <beta|prod>
#   VITE_POSTHOG_KEY / VITE_POSTHOG_HOST (optional) baked into the build.
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
FRONTEND_DIR="$REPO_ROOT/frontend"

# Local deploys: load repo-root .env (CI passes vars/secrets via the shell env).
if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env"
  set +a
fi

BUCKET="$(terraform -chdir="$TF_DIR" output -raw frontend_bucket)"
DIST_ID="$(terraform -chdir="$TF_DIR" output -raw cloudfront_distribution_id)"
API_URL="$(terraform -chdir="$TF_DIR" output -raw api_url)"

# CI: the `config` job writes secrets into terraform-app-config.json (artifact).
# Beta's `deploy` job cannot bind `environment: beta` (OIDC subject must stay
# refs/heads/main), so environment-scoped GitHub secrets are unavailable there —
# read build-time secrets from the artifact instead.
for tfvars in "$REPO_ROOT/terraform-app-config.json" "$TF_DIR/app.auto.tfvars.json"; do
  if [[ -f "$tfvars" ]]; then
    if [[ -z "${POSTHOG_PERSONAL_API_KEY:-}" ]]; then
      POSTHOG_PERSONAL_API_KEY="$(jq -r '.app_secrets.POSTHOG_PERSONAL_API_KEY // empty' "$tfvars")"
    fi
    if [[ -z "${POSTHOG_PROJECT_ID:-}" ]]; then
      POSTHOG_PROJECT_ID="$(jq -r '.app_environment.POSTHOG_PROJECT_ID // empty' "$tfvars")"
    fi
    if [[ -n "${POSTHOG_PERSONAL_API_KEY:-}" && -n "${POSTHOG_PROJECT_ID:-}" ]]; then
      break
    fi
  fi
done

export VITE_API_URL="$API_URL"
export VITE_POSTHOG_KEY="${VITE_POSTHOG_KEY:-${POSTHOG_TOKEN:-}}"
export VITE_POSTHOG_HOST="${VITE_POSTHOG_HOST:-${POSTHOG_HOST:-https://us.i.posthog.com}}"
# Build-time analytics metadata so beta/prod builds are distinguishable in PostHog.
export VITE_APP_ENV="$ENV"
export VITE_GIT_SHA="${GITHUB_SHA:-$(git rev-parse --short HEAD)}"
export POSTHOG_PERSONAL_API_KEY="${POSTHOG_PERSONAL_API_KEY:-${POSTHOG_API_KEY:-}}"
export POSTHOG_PROJECT_ID="${POSTHOG_PROJECT_ID:-}"

if [[ -n "$POSTHOG_PERSONAL_API_KEY" && -n "$POSTHOG_PROJECT_ID" ]]; then
  echo "==> Source maps will upload to PostHog (project $POSTHOG_PROJECT_ID)"
else
  missing=()
  [[ -z "$POSTHOG_PERSONAL_API_KEY" ]] && missing+=("POSTHOG_PERSONAL_API_KEY")
  [[ -z "$POSTHOG_PROJECT_ID" ]] && missing+=("POSTHOG_PROJECT_ID")
  echo "==> Skipping PostHog source map upload (missing: ${missing[*]})"
fi

echo "==> Building SPA (VITE_API_URL=$VITE_API_URL)"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build

echo "==> Syncing to s3://$BUCKET"
aws s3 sync "$FRONTEND_DIR/dist" "s3://$BUCKET" --delete --region "$REGION"

echo "==> Invalidating CloudFront ($DIST_ID)"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --region "$REGION" >/dev/null

echo "Done. Published frontend to $ENV ($API_URL)."
