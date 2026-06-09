---
name: propel-data-pipeline
description: How Propel's ingestion pipeline works — Meltano taps, the custom target-propel loader, the Dagster ingestion job, raw_record/datapoint tables, and dbt status. Use when working under backend/meltano/, backend/app/ingestion/, orchestration/, or transformation/, or when adding a data source, tap, envelope mapper, or metric.
---

# Propel Data Pipeline

```
GitHub API ──Meltano taps──> target-propel ──> Postgres (raw_record + datapoint)
                 ▲                                      │
        Dagster ingestion_job (hourly, per org)         ▼
                                            dbt (transformation/dbt/) — NOT initialized yet
```

Only **GitHub** (+ Copilot metrics) is implemented. Linear/Cursor are roadmap-only (enum entries exist, no taps). `transformation/dbt/` contains just a `.gitkeep` — any dbt work starts with `dbt init`.

## Key files

- `backend/meltano/meltano.yml` — taps + jobs: `github_org_sync`, `github_user_profiles_sync`, `github_commits_sync`, `github_pull_requests_sync`, `github_issues_sync`, `copilot_sync`
- `backend/meltano/target-propel/` — custom Singer target; envelope mappers in `target_propel/envelopes/` (`github.py`, `copilot.py`), wired in `sinks.py::_map_envelope`
- `backend/app/ingestion/orchestrator.py` — run lifecycle: creates `ingestion_run`, mints GitHub App installation token, builds `TAP_*`/`PROPEL_*` env, shells out `meltano run <job>`, finalizes counts/watermark
- `backend/app/ingestion/cli.py` — manual runs
- `orchestration/propel_orchestration/jobs.py` — Dagster `ingestion_job` (one op per resource) + hourly `ingestion_schedule`, fan-out one run per connected org

## Running it

```bash
docker compose up -d ingestion           # Dagster UI at http://localhost:3001
docker compose exec ingestion python -m app.ingestion.cli run
docker compose exec ingestion python -m app.ingestion.cli run --job github_commits_sync
./scripts/dev-ingestion-secrets.sh pull  # GitHub App creds -> .env.ingestion.local
```

## Data contract

- `raw_record` — append-only full payloads, every stream.
- `datapoint` — thin envelope: `kind` (`event`|`measurement`), `tool`, `name`, `subject_type/id`, `occurred_at` or `period_start/end`, `source_key`, `metadata`, `raw_record_id`. Events dedupe on `(tenant_id, source, source_key)`; measurements upsert newest-wins on `(tenant_id, tool, name, subject_id, period_start)` via partial unique indexes.
- All landing tables live in the `public` schema and are tenant-scoped (`tenant_id`). Dagster metadata is isolated in the `dagster` schema.
- Aggregation/metrics are deliberately deferred to dbt — keep envelope mappers thin.

## Adding a new data source

1. Tap(s) + job(s) in `meltano.yml`.
2. Envelope mapper `target_propel/envelopes/<provider>.py`; wire into `sinks.py`.
3. `JobSpec` in orchestrator `JOBS`; auth/env in `_build_env`.
4. Provider in `IntegrationProvider` (`app/models/enums.py`) + connection handling in `app/services/connections.py`.
5. Dagster op + asset key in `jobs.py`, wired into `ingestion_job`.
6. Tests: envelope unit tests, orchestrator tests (Meltano mocked), `target-propel` integration tests.

## Gotchas

- Meltano always runs `--full-refresh`; incrementality comes from orchestrator watermarks (`TAP_GITHUB_START_DATE`, stored in `ingestion_run.cursor`, 1-day overlap), not Singer state. Dedupe is DB-level.
- Each tap-github child sets exactly one of `repositories` / `organizations` / `user_usernames`.
- `github_org_sync` must run before `github_user_profiles_sync` (member logins read from `raw_record`); profiles sync triggers identity linking (`external_identities`, memberships).
- Overlap guard: concurrent run for same (account, resource) is skipped; stale `running` runs (>2h) auto-marked error.
- Copilot: 404 (no Copilot Business) → zero records, not a failure; GitHub caps backfill at ~28 days.
- Ingestion service runs with `SKIP_MIGRATIONS=1` — only the API container migrates.
- `.meltano` lives on a dedicated Docker volume (`meltano-ingestion`) to avoid SQLite lock races.
- `backend/cron/` is legacy; Dagster is the scheduler.
