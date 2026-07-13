#!/usr/bin/env bash
# Resolve the immutable release identifier used for ECR tags and S3 release
# archives. Preference order: IMAGE_TAG / RELEASE_SHA → GITHUB_SHA → git HEAD.
#
# Usage:  source this file, then call resolve_release_sha
# Sets:   RELEASE_SHA (full commit SHA when available)

resolve_release_sha() {
  if [[ -n "${IMAGE_TAG:-}" ]]; then
    RELEASE_SHA="$IMAGE_TAG"
  elif [[ -n "${RELEASE_SHA:-}" ]]; then
    :
  elif [[ -n "${GITHUB_SHA:-}" ]]; then
    RELEASE_SHA="$GITHUB_SHA"
  else
    RELEASE_SHA="$(git rev-parse HEAD)"
  fi

  if [[ -z "$RELEASE_SHA" || "$RELEASE_SHA" == "latest" ]]; then
    echo "error: could not resolve a release SHA (set IMAGE_TAG, RELEASE_SHA, or GITHUB_SHA)" >&2
    return 1
  fi

  export RELEASE_SHA
  echo "$RELEASE_SHA"
}
