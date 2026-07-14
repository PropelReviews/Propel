#!/usr/bin/env bash
# Shared helpers for Propel Cursor hooks.
# Sourced by hook scripts — do not execute directly.

set -euo pipefail

# Cursor bundles its own Node on PATH; strip it so npm/vitest use the project
# toolchain (see https://lirantal.com/blog/cursor-stop-hook-lint-build-verification).
sanitize_path() {
  if command -v python3 >/dev/null 2>&1; then
    PATH="$(
      python3 -c '
import os
skip = (".cursor-server", ".vscode-server")
p = os.environ.get("PATH", "")
print(":".join(x for x in p.split(":")
               if x and not any(s in x for s in skip)))
'
    )"
    export PATH
  fi
}

emit_json() {
  printf '%s\n' "$1"
}

emit_empty() {
  emit_json '{}'
}

hook_log() {
  printf '[propel-hook] %s\n' "$*" >&2
}

truncate_output() {
  local raw="$1"
  local max="${2:-12000}"
  printf '%s' "$raw" | head -c "$max"
}

followup_for_failure() {
  local step="$1"
  local exit_code="$2"
  local raw_output="$3"
  local truncated
  truncated="$(truncate_output "$raw_output")"
  jq -n \
    --arg step "$step" \
    --argjson code "$exit_code" \
    --arg out "$truncated" \
    '{
      followup_message: (
        "The Propel **stop** hook ran automated verification after your last agent turn.\n\n"
        + "**Step:** `\($step)`\n"
        + "**Result:** failed with exit code **\($code)**.\n\n"
        + "Fix the issues below, then continue. Do not skip tests — CI runs the same suite.\n\n"
        + "```text\n"
        + $out
        + "\n```\n"
      )
    }'
}

# Collect changed paths: uncommitted plus commits on this branch since main.
collect_changed_paths() {
  local root="$1"
  cd "$root"

  {
    git diff --name-only HEAD 2>/dev/null || true
    git diff --name-only --cached HEAD 2>/dev/null || true
    local base
    base="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD origin/main 2>/dev/null || echo "")"
    if [[ -n "$base" ]]; then
      git diff --name-only "${base}...HEAD" 2>/dev/null || true
    fi
  } | sed '/^$/d' | sort -u
}

postgres_ready() {
  command -v pg_isready >/dev/null 2>&1 \
    && pg_isready -h localhost -p 5432 -q 2>/dev/null
}

is_feature_code_path() {
  local path="$1"
  case "$path" in
    .cursor/* | */node_modules/* | */.venv/* | */dist/* | */dist-landing/*)
      return 1
      ;;
    uv.lock | frontend/package-lock.json)
      return 1
      ;;
    */tests/* | */test_* | *_test.py | *.test.tsx | *.browser.test.tsx)
      return 1
      ;;
    backend/* | frontend/src/* | orchestration/* | transformation/* | infrastructure/* | scripts/* | ee/*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_doc_path() {
  local path="$1"
  case "$path" in
    docs/* | README.md | CONTRIBUTING.md | */README.md)
      return 0
      ;;
    *.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_frontend_visual_path() {
  local path="$1"
  case "$path" in
    frontend/src/components/* | frontend/src/pages/*)
      case "$path" in
        *.test.tsx | *.browser.test.tsx) return 1 ;;
        *.tsx | *.ts) return 0 ;;
      esac
      ;;
  esac
  return 1
}

browser_tests_for_changes() {
  local root="$1"
  shift
  local path rel base dir candidate
  declare -A seen=()

  for path in "$@"; do
    is_frontend_visual_path "$path" || continue
    rel="${path#frontend/}"
    base="$(basename "$rel")"
    base="${base%.*}"
    dir="$(dirname "$rel")"
    candidate="${root}/frontend/${dir}/${base}.browser.test.tsx"
    if [[ -f "$candidate" ]]; then
      seen["$candidate"]=1
    fi
  done

  if [[ "${#seen[@]}" -eq 0 ]]; then
    return 0
  fi

  for candidate in "${!seen[@]}"; do
    printf '%s\n' "$candidate"
  done
}
