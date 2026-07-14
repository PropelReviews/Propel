# Cursor agent integration

Propel ships project-level [Cursor hooks](https://cursor.com/docs/hooks) in
`.cursor/hooks.json`. They run for local Agent sessions and for [cloud
agents](https://cursor.com/docs/cloud-agent) (repo hooks are loaded from the
committed `.cursor/hooks.json`; user-level `~/.cursor/hooks.json` hooks do not
run in the cloud).

## Hook summary

| When | Hook | What it does |
|------|------|--------------|
| After each file edit (`Write`, `StrReplace`, `EditNotebook`) | `check-format.sh` | Prettier `format:check` on edited `frontend/` files |
| After each file edit | `check-ruff.sh` | `ruff format --check` + `ruff check` on edited `backend/` Python |
| After each agent turn (`stop`) | `stop-verify.sh` | Runs targeted tests; prompts doc updates when feature code changed without docs |

Formatting hooks inject `additional_context` into the agent loop when checks
fail so the model can fix issues before continuing.

The `stop` hook can return a `followup_message`, which Cursor submits as the
next user message — a bounded self-healing loop (`loop_limit: 8`). On success
it prints `{}` so the conversation can end normally.

## Stop-hook verification

`stop-verify.sh` inspects changed files (uncommitted diff plus commits on the
current branch since `main`) and runs only the suites that apply:

| Changed paths | Tests run |
|---------------|-----------|
| `backend/` (excluding `tests/`) | `uv run alembic upgrade head && uv run pytest` when Postgres is on `localhost:5432` |
| `frontend/src/` (non-test files) | Vitest **unit** project |
| `frontend/src/components/` or `frontend/src/pages/` | Vitest **browser** project (Playwright Chromium). Colocated `*.browser.test.tsx` files run when present; otherwise the full browser project runs |
| `orchestration/`, `scripts/*.py` | Backend pytest (same Postgres requirement) |

If Postgres is not running locally, backend tests are skipped with a log line;
CI still enforces the full backend suite on pull requests.

### Documentation follow-up

When feature code changes but no documentation paths change, the stop hook asks
the agent to update docs before finishing. Documentation includes:

- `docs/**`
- `README.md` / `CONTRIBUTING.md` at any level
- Component READMEs (`backend/README.md`, `frontend/README.md`, etc.)

Test-only edits, lockfiles, and `.cursor/` changes do not count as feature work.

## Cloud agent setup

`.cursor/environment.json` runs `scripts/cloud-setup.sh` before each cloud
session. That script installs frontend and backend dependencies and downloads
Playwright Chromium for browser tests.

## Related files

- `.cursor/hooks.json` — hook registration
- `.cursor/hooks/lib/common.sh` — shared helpers
- `.cursor/rules/format-check.mdc` — workspace rule for Prettier
- `.cursor/agents/visual-test-writer.md` — subagent for writing browser tests
- `.cursor/skills/propel-*` — component conventions for agents

## Debugging

Hook diagnostics go to **stderr** (look for `[propel-hook]`). Only JSON may be
written to stdout.

To exercise the stop hook manually:

```bash
printf '%s\n' '{"status":"completed","loop_count":0}' | .cursor/hooks/stop-verify.sh
```

If hooks do not reload after editing `hooks.json`, restart Cursor.
