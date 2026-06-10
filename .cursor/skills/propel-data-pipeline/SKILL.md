---
name: propel-data-pipeline
description: How Propel's ingestion pipeline works — Meltano taps, the custom target-propel loader, the Dagster ingestion job, raw_record/datapoint tables, and dbt status. Use when working under backend/meltano/, backend/app/ingestion/, orchestration/, or transformation/, or when adding a data source, tap, envelope mapper, or metric.
---

# Propel Data Pipeline

```
GitHub API ──Meltano taps──> target-propel ──> Postgres (raw_record + datapoint)
                 ▲                                      │
   Dagster: discovery_job (hourly) ──sensor──>          ▼
   org_ingestion_job (per org) ──sensor──> dbt assets (transformation/dbt/)
                                           └─> Postgres `analytics` schema (marts)
```

Only **GitHub** (+ Copilot metrics) is implemented. Linear/Cursor are roadmap-only (enum entries exist, no taps). The whole pipeline is an event-driven job chain: hourly `discovery_job` → `org_fanout_sensor` launches one `org_ingestion_job` per org → `analytics_sensor` runs the dbt assets for that org's tenant partition (`dbt build --vars '{tenant_id: ...}'`, incremental delete+insert).

## Key files

- `backend/meltano/meltano.yml` — taps + jobs: `github_org_sync`, `github_user_profiles_sync`, `github_commits_sync`, `github_pull_requests_sync`, `github_issues_sync`, `copilot_sync`
- `backend/meltano/target-propel/` — custom Singer target; envelope mappers in `target_propel/envelopes/` (`github.py`, `copilot.py`), wired in `sinks.py::_map_envelope`
- `backend/app/ingestion/orchestrator.py` — run lifecycle: creates `ingestion_run`, mints GitHub App installation token, builds `TAP_*`/`PROPEL_*` env, shells out `meltano run <job>`, finalizes counts/watermark; `start_date` kwarg overrides the watermark for backfills
- `backend/app/ingestion/cli.py` — manual runs (`--account-id`, `--job`, `--start-date`)
- `orchestration/propel_orchestration/jobs.py` — `discovery_job` + hourly `discovery_schedule`, per-org `org_ingestion_job` (one op per resource), `org_fanout_sensor`
- `orchestration/propel_orchestration/analytics.py` — dagster-dbt assets (tenant `DynamicPartitionsDefinition`), `analytics_assets_job`, `analytics_sensor`; derives `DBT_*` env from `DATABASE_URL`
- `transformation/dbt/` — dbt project: `staging/stg_github_pull_requests` (latest PR snapshot from `raw_record`) → `marts/fct_pr_activity_daily` (incremental per tenant/day, `analytics` schema)
- `backend/app/{routers,services,schemas}/metrics.py` — tenant-scoped API over the marts (`date_trunc` per granularity)

## Running it

```bash
docker compose up -d ingestion           # Dagster UI at http://localhost:3001
docker compose exec ingestion python -m app.ingestion.cli run
docker compose exec ingestion python -m app.ingestion.cli run --job github_commits_sync
docker compose exec ingestion python -m app.ingestion.cli run --start-date 2026-01-01  # backfill
./scripts/dev-ingestion-secrets.sh pull  # GitHub App creds -> .env.ingestion.local

# dbt manually (Dagster runs it automatically after each org ingestion)
docker compose exec ingestion dbt build --full-refresh \
  --project-dir /transformation/dbt --profiles-dir /transformation/dbt

# dbt lint (config: transformation/dbt/.sqlfluff; CI gate in .github/workflows/ci.yml "dbt checks")
cd transformation/dbt && uvx --from "sqlfluff>=3,<4" sqlfluff lint models
```

## Data contract

- `raw_record` — append-only full payloads, every stream.
- `datapoint` — thin envelope: `kind` (`event`|`measurement`), `tool`, `name`, `subject_type/id`, `occurred_at` or `period_start/end`, `source_key`, `metadata`, `raw_record_id`. Events dedupe on `(tenant_id, source, source_key)`; measurements upsert newest-wins on `(tenant_id, tool, name, subject_id, period_start)` via partial unique indexes.
- All landing tables live in the `public` schema and are tenant-scoped (`tenant_id`). Dagster metadata is isolated in the `dagster` schema; dbt marts land in the `analytics` schema (dbt-owned, no Alembic).
- Aggregation/metrics belong in dbt models (read `raw_record`, not `datapoint`, for entities whose state mutates — datapoint events freeze at first ingest) — keep envelope mappers thin.

## Adding a new data source

1. Tap(s) + job(s) in `meltano.yml`.
2. Envelope mapper `target_propel/envelopes/<provider>.py`; wire into `sinks.py`.
3. `JobSpec` in orchestrator `JOBS`; auth/env in `_build_env`.
4. Provider in `IntegrationProvider` (`app/models/enums.py`) + connection handling in `app/services/connections.py`.
5. Dagster op + asset key in `jobs.py`, wired into `org_ingestion_job` (and an `AssetSpec` in `analytics.py` for lineage).
6. Tests: envelope unit tests, orchestrator tests (Meltano mocked), `target-propel` integration tests.

## Gotchas

- Meltano always runs `--full-refresh`; incrementality comes from orchestrator watermarks (`TAP_GITHUB_START_DATE`, stored in `ingestion_run.cursor`, 1-day overlap), not Singer state. Dedupe is DB-level.
- Each tap-github child sets exactly one of `repositories` / `organizations` / `user_usernames`.
- `github_org_sync` must run before `github_user_profiles_sync` (member logins read from `raw_record`); profiles sync triggers identity linking (`external_identities`, memberships).
- Overlap guard: concurrent run for same (account, resource) is skipped; stale `running` runs (>2h) auto-marked error.
- Copilot: the orchestrator probes `/orgs/{org}/copilot/metrics` first and skips `copilot_sync` when unavailable (result cached 24h on `connected_accounts.metadata`); the tap also tolerates 404/403/422 as zero records, not a failure. GitHub caps backfill at ~28 days.
- Ingestion service runs with `SKIP_MIGRATIONS=1` — only the API container migrates.
- `.meltano` lives on a dedicated Docker volume (`meltano-ingestion`) to avoid SQLite lock races.
- `backend/cron/` is legacy; Dagster is the scheduler.
