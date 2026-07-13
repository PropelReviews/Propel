#!/usr/bin/env bash
#
# Configure GitHub branch protection / ruleset so PRs cannot merge to main
# unless the aggregate ``CI success`` check is green.
#
# Requires: gh auth with admin:repo (or org ruleset) scope.
#
# Usage:
#   ./scripts/configure-branch-protection.sh
#   REPO=PropelReviews/Propel ./scripts/configure-branch-protection.sh
set -euo pipefail

REPO="${REPO:-PropelReviews/Propel}"
RULESET_NAME="main — require CI success"

echo "==> Ensuring ruleset on $REPO: $RULESET_NAME"

# Look up an existing ruleset with this name so re-runs are idempotent.
EXISTING_ID="$(
  gh api "repos/$REPO/rulesets" --jq \
    ".[] | select(.name == \"$RULESET_NAME\") | .id" \
    | head -n1 || true
)"

BODY="$(jq -n \
  --arg name "$RULESET_NAME" \
  '{
    name: $name,
    target: "branch",
    enforcement: "active",
    conditions: {
      ref_name: {
        include: ["refs/heads/main"],
        exclude: []
      }
    },
    bypass_actors: [],
    rules: [
      { type: "deletion" },
      { type: "non_fast_forward" },
      {
        type: "pull_request",
        parameters: {
          required_approving_review_count: 1,
          dismiss_stale_reviews_on_push: true,
          require_code_owner_review: false,
          require_last_push_approval: false,
          required_review_thread_resolution: true,
          allowed_merge_methods: ["merge", "squash", "rebase"]
        }
      },
      {
        type: "required_status_checks",
        parameters: {
          strict_required_status_checks_policy: true,
          do_not_enforce_on_create: false,
          required_status_checks: [
            { context: "CI success" }
          ]
        }
      }
    ]
  }')"

if [[ -n "$EXISTING_ID" ]]; then
  echo "==> Updating ruleset id=$EXISTING_ID"
  echo "$BODY" | gh api "repos/$REPO/rulesets/$EXISTING_ID" -X PUT --input -
else
  echo "==> Creating ruleset"
  echo "$BODY" | gh api "repos/$REPO/rulesets" -X POST --input -
fi

echo "Done. Merges to main now require a green \"CI success\" check (and 1 approval)."
