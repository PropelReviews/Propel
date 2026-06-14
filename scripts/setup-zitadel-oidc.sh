#!/usr/bin/env bash
# Bootstrap a Zitadel OIDC application for the Propel BFF (local dev).
#
# ⚠️  LOCAL DEVELOPMENT ONLY — values printed here are for your laptop. Use
#     Secrets Manager / unique credentials in beta and prod (see docs/deployment/zitadel.md).
#
# Prerequisites: docker compose up (zitadel + postgres healthy).
#
# Usage:
#   ./scripts/setup-zitadel-oidc.sh
#
# Prints export lines for .env — add ZITADEL_CLIENT_ID and ZITADEL_CLIENT_SECRET.

set -euo pipefail

ZITADEL_URL="${ZITADEL_ISSUER:-http://localhost:8080}"
REDIRECT_URI="${OAUTH_CALLBACK_BASE_URL:-http://localhost:8000}/api/v1/auth/callback"

echo "==> Waiting for Zitadel at ${ZITADEL_URL}..."
for _ in $(seq 1 60); do
  if curl -sf "${ZITADEL_URL}/.well-known/openid-configuration" >/dev/null; then
    break
  fi
  sleep 2
done

echo "==> Zitadel is up."
echo ""
echo "Manual step (first run): open ${ZITADEL_URL} and complete the default"
echo "instance setup if prompted. Then create a Project + OIDC Web application:"
echo "  - Redirect URI: ${REDIRECT_URI}"
echo "  - Auth method: PKCE (or client secret + PKCE)"
echo "  - Grant types: Authorization Code"
echo "  - Scopes: openid, email, profile, urn:zitadel:iam:org:id, urn:zitadel:iam:org:name"
echo ""
echo "Add to .env:"
echo "  ZITADEL_ISSUER=${ZITADEL_URL}"
echo "  ZITADEL_CLIENT_ID=<from Zitadel console>"
echo "  ZITADEL_CLIENT_SECRET=<from Zitadel console>"
echo "  SESSION_SECRET=\$(openssl rand -hex 32)"
echo "  OAUTH_CALLBACK_BASE_URL=${OAUTH_CALLBACK_BASE_URL:-http://localhost:8000}"
