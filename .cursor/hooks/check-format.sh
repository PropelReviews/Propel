#!/usr/bin/env bash
# Runs Prettier format:check on frontend files after agent edits.
# Injects additional_context when formatting fails so the agent fixes it.

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

frontend_dir="${cwd%/}/frontend"
case "$file_path" in
  "${frontend_dir}/"*) ;;
  *) exit 0 ;;
esac

rel_path="${file_path#"${frontend_dir}/"}"

case "$rel_path" in
  node_modules/* | dist/* | dist-landing/* | storybook-static/* | __screenshots__/*)
    exit 0
    ;;
esac

ext="${rel_path##*.}"
case "$ext" in
  ts | tsx | js | jsx | json | css | html | md | mdx | yml | yaml) ;;
  *) exit 0 ;;
esac

prettier="${frontend_dir}/node_modules/.bin/prettier"
if [[ ! -x "$prettier" ]]; then
  echo '{"additional_context": "Prettier is not installed in frontend/. Run `cd frontend && npm install` before editing frontend files."}'
  exit 0
fi

output=""
if ! output="$(
  cd "$frontend_dir" && "$prettier" --check "$rel_path" 2>&1
)"; then
  payload="$(jq -n \
    --arg file "$rel_path" \
    --arg details "$output" \
    '{
      additional_context: (
        "FORMAT CHECK FAILED for frontend/\($file). "
        + "Fix with `cd frontend && npm run format`, then verify with `npm run format:check` before continuing.\n\n"
        + $details
      )
    }')"
  echo "$payload"
fi

exit 0
