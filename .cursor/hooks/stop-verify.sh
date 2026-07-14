#!/usr/bin/env bash
# Runs after each agent turn (stop hook):
#   1. Detects files changed in this session / branch
#   2. Runs targeted tests (backend pytest, frontend unit, browser visual tests)
#   3. When tests pass and feature code changed without doc updates, asks the
#      agent to update documentation before finishing.
#
# Returns JSON on stdout: {} on success, or {"followup_message": "..."} to loop.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

sanitize_path

input="$(cat)"
status="completed"
loop_count=0

if command -v jq >/dev/null 2>&1; then
  set +e
  status="$(printf '%s' "$input" | jq -r '.status // "completed"' 2>/dev/null)"
  loop_count="$(printf '%s' "$input" | jq -r '.loop_count // 0' 2>/dev/null)"
  set -e
fi

if [[ "$status" == "aborted" ]]; then
  hook_log "stop-verify: status=aborted — skipping verification"
  emit_empty
  exit 0
fi

root="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$root"

mapfile -t changed < <(collect_changed_paths "$root")
if [[ "${#changed[@]}" -eq 0 ]]; then
  hook_log "stop-verify: no changed files detected"
  emit_empty
  exit 0
fi

hook_log "stop-verify: ${#changed[@]} changed path(s)"

run_backend=false
run_frontend_unit=false
run_frontend_browser=false
declare -a browser_test_files=()

for path in "${changed[@]}"; do
  case "$path" in
    backend/*)
      case "$path" in
        backend/tests/*) ;;
        *) run_backend=true ;;
      esac
      ;;
    frontend/src/*)
      case "$path" in
        *.test.tsx | *.browser.test.tsx) ;;
        *) run_frontend_unit=true ;;
      esac
      if is_frontend_visual_path "$path"; then
        run_frontend_browser=true
      fi
      ;;
    orchestration/* | scripts/*.py)
      run_backend=true
      ;;
  esac
done

if $run_frontend_browser; then
  mapfile -t browser_test_files < <(
    browser_tests_for_changes "$root" "${changed[@]}"
  )
fi

hook_log "stop-verify: backend=$run_backend unit=$run_frontend_unit browser=$run_frontend_browser browser_tests=${#browser_test_files[@]}"

fail_step=""
fail_code=0
fail_output=""

run_step() {
  local step="$1"
  shift
  hook_log "running: $step"
  local output=""
  local code=0
  set +e
  output="$("$@" 2>&1)"
  code=$?
  set -e
  if [[ "$code" -ne 0 ]]; then
    fail_step="$step"
    fail_code="$code"
    fail_output="$output"
    return 1
  fi
  return 0
}

if [[ -z "$fail_step" ]] && $run_backend; then
  if postgres_ready; then
    run_step \
      "cd backend && uv run alembic upgrade head && uv run pytest -v --tb=short" \
      bash -lc 'cd backend && uv run alembic upgrade head && uv run pytest -v --tb=short' \
      || true
  else
    hook_log "postgres not on localhost:5432 — skipping backend pytest (CI will run it)"
  fi
fi

if [[ -z "$fail_step" ]] && ( $run_frontend_unit || $run_frontend_browser ); then
  if [[ ! -d "${root}/frontend/node_modules" ]]; then
    fail_step="cd frontend && npm install"
    fail_code=1
    fail_output="frontend/node_modules is missing. Run: cd frontend && npm install"
  fi
fi

if [[ -z "$fail_step" ]] && $run_frontend_unit; then
  run_step \
    "cd frontend && npx vitest run --project unit --passWithNoTests" \
    bash -lc 'cd frontend && npx vitest run --project unit --passWithNoTests' \
    || true
fi

if [[ -z "$fail_step" ]] && $run_frontend_browser; then
  if ! command -v chromium >/dev/null 2>&1 \
    && [[ ! -d "${HOME}/.cache/ms-playwright" ]]; then
    hook_log "installing playwright chromium for browser tests"
    bash -lc 'cd frontend && npx playwright install chromium' >&2 || true
  fi

  if [[ "${#browser_test_files[@]}" -gt 0 ]]; then
    rel_files=()
    for abs in "${browser_test_files[@]}"; do
      rel_files+=("${abs#${root}/frontend/}")
    done
    browser_cmd="cd frontend && npx vitest run --project browser ${rel_files[*]}"
    run_step "$browser_cmd" bash -lc "$browser_cmd" || true
  else
    run_step \
      "cd frontend && npx vitest run --project browser --passWithNoTests" \
      bash -lc 'cd frontend && npx vitest run --project browser --passWithNoTests' \
      || true
  fi
fi

if [[ -n "$fail_step" ]]; then
  emit_json "$(followup_for_failure "$fail_step" "$fail_code" "$fail_output")"
  exit 0
fi

feature_changed=false
docs_changed=false

for path in "${changed[@]}"; do
  if is_feature_code_path "$path"; then
    feature_changed=true
  fi
  if is_doc_path "$path"; then
    docs_changed=true
  fi
done

if $feature_changed && ! $docs_changed; then
  emit_json "$(jq -n \
    --arg paths "$(printf '%s\n' "${changed[@]}" | head -20)" \
    '{
      followup_message: (
        "The Propel **stop** hook detected feature code changes without matching documentation updates.\n\n"
        + "Before finishing this task, update documentation:\n"
        + "- Add or update relevant files under `docs/` (see `docs/README.md` for the index)\n"
        + "- Update component READMEs when setup, APIs, or behavior change (`backend/README.md`, `frontend/README.md`, etc.)\n"
        + "- Update `CONTRIBUTING.md` only when contribution workflow changes\n\n"
        + "Changed paths (sample):\n```text\n"
        + $paths
        + "\n```\n\n"
        + "After updating docs, confirm tests still pass and summarize what you documented."
      )
    }')"
  exit 0
fi

emit_empty
exit 0
