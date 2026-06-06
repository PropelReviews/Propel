#!/usr/bin/env bash
#
# Build the Vite SPA for an environment, sync it to the S3 bucket, and
# invalidate CloudFront. Reads identifiers from Terraform outputs.
#
# Each deploy also archives the build under s3://$BUCKET/releases/$SHA/ so
# scripts/rollback.sh can restore a previous release without rebuilding.
#
# Usage: scripts/deploy-frontend.sh <beta|prod>
#   VITE_POSTHOG_KEY / VITE_POSTHOG_HOST (optional) baked into the build.
#   IMAGE_TAG / RELEASE_SHA / GITHUB_SHA — release archive key (default: git HEAD).
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
# shellcheck source=lib/release-sha.sh
source "$REPO_ROOT/scripts/lib/release-sha.sh"

TF_DIR="$REPO_ROOT/infrastructure/terraform/environments/$ENV"
FRONTEND_DIR="$REPO_ROOT/frontend"
SHA="$(resolve_release_sha)"

BUCKET="$(terraform -chdir="$TF_DIR" output -raw frontend_bucket)"
DIST_ID="$(terraform -chdir="$TF_DIR" output -raw cloudfront_distribution_id)"
API_URL="$(terraform -chdir="$TF_DIR" output -raw api_url)"

export VITE_API_URL="$API_URL"
export VITE_POSTHOG_KEY="${VITE_POSTHOG_KEY:-${POSTHOG_TOKEN:-}}"
export VITE_POSTHOG_HOST="${VITE_POSTHOG_HOST:-${POSTHOG_HOST:-https://us.i.posthog.com}}"
# Build-time analytics metadata so beta/prod builds are distinguishable in PostHog.
export VITE_APP_ENV="$ENV"
export VITE_GIT_SHA="${SHA:0:12}"
export POSTHOG_PERSONAL_API_KEY="${POSTHOG_PERSONAL_API_KEY:-${POSTHOG_API_KEY:-}}"
export POSTHOG_PROJECT_ID="${POSTHOG_PROJECT_ID:-}"

if [[ -n "$POSTHOG_PERSONAL_API_KEY" && -n "$POSTHOG_PROJECT_ID" ]]; then
  echo "==> Source maps will upload to PostHog (project $POSTHOG_PROJECT_ID)"
else
  echo "==> Skipping PostHog source map upload (set POSTHOG_PERSONAL_API_KEY + POSTHOG_PROJECT_ID to enable)"
fi

echo "==> Building SPA (VITE_API_URL=$VITE_API_URL, release=$SHA)"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build

echo "==> Archiving release to s3://$BUCKET/releases/$SHA/"
aws s3 sync "$FRONTEND_DIR/dist" "s3://$BUCKET/releases/$SHA/" \
  --delete --region "$REGION"

echo "==> Syncing live site to s3://$BUCKET (preserving releases/)"
aws s3 sync "$FRONTEND_DIR/dist" "s3://$BUCKET" \
  --delete \
  --exclude "releases/*" \
  --region "$REGION"

echo "==> Invalidating CloudFront ($DIST_ID)"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --region "$REGION" >/dev/null

echo "Done. Published frontend to $ENV ($API_URL) as release $SHA."
