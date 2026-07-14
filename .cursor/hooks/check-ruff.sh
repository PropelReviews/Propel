#!/usr/bin/env bash
# Runs ruff format --check and ruff check on backend Python files after agent
# edits. Injects additional_context when ruff fails so the agent fixes it before
# moving on (mirrors check-format.sh, which does the same for the frontend).

set -euo pipefail

input="$(cat)"

tool_name="$(echo "$input" | jq -r '.tool_name // empty')"
[[ -n "$tool_name" ]] || exit 0

cwd="$(echo "$input" | jq -r '.cwd // empty')"
[[ -n "$cwd" && "$cwd" != "null" ]] || cwd="$(pwd)"

file_path="$(echo "$input" | jq -r '
  (.tool_input
    | if type == "string" then (fromjson? // empty) else . end) as $ti
  | if .tool_name == "EditNotebook" then $ti.target_notebook // empty
    else $ti.path // empty
    end
')"

[[ -n "$file_path" && "$file_path" != "null" ]] || exit 0

# Resolve to an absolute path.
if [[ "$file_path" != /* ]]; then
  file_path="${cwd%/}/${file_path}"
fi

backend_dir="${cwd%/}/backend"
case "$file_path" in
  "${backend_dir}/"*) ;;
  *) exit 0 ;;
esac

rel_path="${file_path#"${backend_dir}/"}"

case "$rel_path" in
  .venv/* | */.venv/* | __pycache__/* | */__pycache__/* | .meltano/* | */.meltano/*)
    exit 0
    ;;
esac

ext="${rel_path##*.}"
[[ "$ext" == "py" ]] || exit 0

# Prefer the dev venv's ruff; fall back to uv (no sync, so it never mutates the
# environment just to lint).
ruff_bin="${backend_dir}/.venv/bin/ruff"
if [[ -x "$ruff_bin" ]]; then
  ruff_cmd=("$ruff_bin")
elif command -v uv >/dev/null 2>&1; then
  ruff_cmd=(uv run --no-sync ruff)
else
  echo '{"additional_context": "ruff is not available. Run `cd backend && uv sync` before editing Python files."}'
  exit 0
fi

output=""
status=0

# NO_COLOR keeps ANSI escapes out of the injected context.
if ! fmt_out="$(cd "$backend_dir" && NO_COLOR=1 "${ruff_cmd[@]}" format --check "$rel_path" 2>&1)"; then
  status=1
  output+="$fmt_out"$'\n'
fi

if ! lint_out="$(cd "$backend_dir" && NO_COLOR=1 "${ruff_cmd[@]}" check "$rel_path" 2>&1)"; then
  status=1
  output+="$lint_out"$'\n'
fi

if [[ "$status" -ne 0 ]]; then
  # Strip ANSI escape sequences so the injected context is plain text.
  output="$(printf '%s' "$output" | sed -E $'s/\x1b\\[[0-9;]*m//g')"
  payload="$(jq -n \
    --arg file "$rel_path" \
    --arg details "$output" \
    '{
      additional_context: (
        "RUFF CHECK FAILED for backend/\($file). "
        + "Fix with `cd backend && uv run ruff format . && uv run ruff check --fix .`, "
        + "then verify with `uv run ruff format --check . && uv run ruff check .` before continuing.\n\n"
        + $details
      )
    }')"
  echo "$payload"
fi

exit 0
