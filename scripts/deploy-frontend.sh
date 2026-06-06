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

BUCKET="$(terraform -chdir="$TF_DIR" output -raw frontend_bucket)"
DIST_ID="$(terraform -chdir="$TF_DIR" output -raw cloudfront_distribution_id)"
API_URL="$(terraform -chdir="$TF_DIR" output -raw api_url)"

export VITE_API_URL="$API_URL"
export VITE_POSTHOG_KEY="${VITE_POSTHOG_KEY:-${POSTHOG_TOKEN:-}}"
export VITE_POSTHOG_HOST="${VITE_POSTHOG_HOST:-${POSTHOG_HOST:-https://us.i.posthog.com}}"
# Build-time analytics metadata so beta/prod builds are distinguishable in PostHog.
export VITE_APP_ENV="$ENV"
export VITE_GIT_SHA="${GITHUB_SHA:-$(git rev-parse --short HEAD)}"

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
