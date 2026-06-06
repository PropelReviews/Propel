#!/usr/bin/env bash
#
# Build the marketing landing site for an environment, sync it to the landing
# S3 bucket, and invalidate CloudFront. Reads identifiers from Terraform
# outputs. Mirrors deploy-frontend.sh but targets the apex/www distribution.
#
# Usage: scripts/deploy-landing.sh <beta|prod>
#   VITE_POSTHOG_KEY / VITE_POSTHOG_HOST (optional) baked into the build.
#   VITE_GITHUB_URL (optional) overrides the repository link in the CTAs.
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

BUCKET="$(terraform -chdir="$TF_DIR" output -raw landing_bucket)"
DIST_ID="$(terraform -chdir="$TF_DIR" output -raw landing_cloudfront_distribution_id)"
APP_URL="$(terraform -chdir="$TF_DIR" output -raw frontend_url)"

# CTAs point at the app frontend for this environment (e.g. app.beta.propel.ninja).
export VITE_APP_URL="$APP_URL"
export VITE_GITHUB_URL="${VITE_GITHUB_URL:-https://github.com/PropelReviews/Propel}"
export VITE_POSTHOG_KEY="${VITE_POSTHOG_KEY:-${POSTHOG_TOKEN:-}}"
export VITE_POSTHOG_HOST="${VITE_POSTHOG_HOST:-${POSTHOG_HOST:-https://us.i.posthog.com}}"

echo "==> Building landing site (VITE_APP_URL=$VITE_APP_URL)"
npm --prefix "$FRONTEND_DIR" ci
npm --prefix "$FRONTEND_DIR" run build:landing

echo "==> Syncing to s3://$BUCKET"
aws s3 sync "$FRONTEND_DIR/dist-landing" "s3://$BUCKET" --delete --region "$REGION"

echo "==> Invalidating CloudFront ($DIST_ID)"
aws cloudfront create-invalidation \
  --distribution-id "$DIST_ID" \
  --paths "/*" \
  --region "$REGION" >/dev/null

echo "Done. Published landing to $ENV ($APP_URL)."
