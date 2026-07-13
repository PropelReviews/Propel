# Propel Orchestration (Dagster)

Dagster orchestrates Propel's ingestion **and** analytics. It runs as a
long-running ECS service (daemon + webserver). The extraction pipeline itself
(Meltano taps + `target-propel`) lives in [`../backend`](../backend); the dbt
models live in [`../transformation/dbt`](../transformation).

The pipeline is an event-driven job chain (sensors, not per-org cron):

```
hourly ──> discovery_job ──org_fanout_sensor──> org_ingestion_job (x N orgs)
                                                       │
                                              analytics_sensor (per success)
                                                       ▼
                                  analytics_assets_job (dbt, tenant partition)
```

Per-org ingestion DAG:

```
start_org_ingestion ─┬─> get_org_members ──> get_user_profiles ─┐
                     ├─> get_commits ───────────────────────────┤
                     ├─> get_pull_requests ─────────────────────┤
                     ├─> get_issues ────────────────────────────┤
                     ├─> get_releases ──────────────────────────┤
                     └─> get_copilot_usage ─────────────────────┴─> flush_logs
```

- **`discovery_job`** (hourly via `discovery_schedule`) reconciles
  `connected_accounts` against the GitHub App's installations.
- **One run per org.** `org_fanout_sensor` fires on discovery success and emits
  a `RunRequest` per active org, tagged `propel/account_id` + `propel/org`.
  Each op reads the tag and calls
  `orchestrator.run_all(account_id=..., job_name=...)` scoped to that org, so a
  slow or failing org is isolated to its own run/UI entry. Launching
  `org_ingestion_job` manually with no tag processes every active org in one
  run.
- **Incremental + backfills.** Raw pulls are watermark-driven (per
  account/resource, 1-day overlap, DB-level dedupe). Tag a manual launch with
  `propel/start_date` (ISO date) to re-pull history from that date; the
  analytics sensor recomputes the tenant's metrics automatically afterwards.
- `get_user_profiles` runs after `get_org_members` (it targets the discovered
  member logins). `flush_logs` fans in last to drain the OTLP batch handler.
- **Analytics (dbt assets).** `analytics.py` loads `transformation/dbt` via
  `dagster-dbt`, so every model is a software-defined asset with lineage from
  the ingestion assets (`github/releases` → `stg_github_releases` →
  `fct_deployment_frequency_daily`, plus PR/review marts) and dbt tests as asset checks. Assets are
  partitioned by tenant (`DynamicPartitionsDefinition("tenant")`);
  `analytics_sensor` registers partitions and requests one tenant-scoped run
  (`dbt build --vars '{tenant_id: ...}'`) per successful org ingestion run.
  Runs carry `dagster/concurrency_key: dbt` and queue (limit 1, see
  `dagster.yaml`) so delete+insert never races. Ingestion jobs carry
  `dagster/concurrency_key: ingestion` (limit matches `DASK_WORKER_MAX`) so
  EcsRunLauncher does not stampede Fargate at hourly fan-out. Backfill any subset of tenants
  from the UI's partition view.
- **Ingestion assets.** Each resource op emits an `AssetMaterialization` per
  `ingestion_run` (asset keys `github/commits`, `github/issues`, …) with
  `records_pulled` / `datapoints_written` / org metadata; matching `AssetSpec`s
  make them real upstream nodes in the lineage graph.

```
orchestration/
  pyproject.toml                      deps: dagster + dagster-dbt + dbt + backend runtime deps
  dagster.yaml                        prod Postgres storage + run concurrency + monitoring
  workspace.yaml                      code location -> propel_orchestration.definitions
  scripts/prepare_dagster_db.py       creates the `dagster` schema, prints DAGSTER_PG_URL
  run_launcher_ecs.yaml               PropelEcsRunLauncher config (prod ECS only)
  propel_orchestration/
    ecs_run_launcher.py               prepends /entrypoint.sh to EcsRunLauncher commands
    definitions.py                    Definitions(assets, jobs, schedules, sensors, resources)
    jobs.py                           discovery_job + org_ingestion_job + schedule + fan-out sensor
    analytics.py                      dbt assets, tenant partitions, analytics sensor
    logging.py                        OTLP -> PostHog as service.name=propel-ingestion
```

## How it runs

- The webserver and daemon load `propel_orchestration.definitions`. The ops
  import the backend `app` package, which is made importable via `PYTHONPATH`
  (not installed as a wheel) so the same source serves both projects.
- `discovery_schedule` auto-starts (`DefaultScheduleStatus.RUNNING`) and fires
  `0 * * * *` (UTC); both sensors also auto-start.
- dbt connection credentials (`DBT_*`) are derived from `DATABASE_URL` at
  module import (`analytics.py`); the dbt manifest is parsed on code-location
  load in dev (`prepare_if_dev`) and baked at image build in prod.
- Dagster's run/event/schedule storage shares the app's Postgres but lives in a
  dedicated `dagster` schema (see `scripts/prepare_dagster_db.py`) so its own
  `alembic_version` never collides with the app's migrations.

## Observability

Run logs (`context.log` and `propel.*` Python loggers) are emitted to **stdout**
via `python_logs` in `dagster.yaml`, so they show up in `docker logs -f
propel-ingestion` locally without opening the Dagster UI. Event-log storage in
Postgres is unchanged — the UI still works.

Structured logs also ship to PostHog as `service.name = propel-ingestion` when
`POSTHOG_TOKEN` is set. Useful events:

| Event | Meaning |
| --- | --- |
| `ingestion.startup` | readiness check (DB reachable, Meltano installed, GitHub App + PostHog configured) |
| `extraction.discover` | installed orgs (installations) found for this run |
| `dagster.op` | per-resource op lifecycle (start / success / error, duration, `ingestion.job`) |
| `extraction.batch` / `extraction.run` / `extraction.meltano` | orchestrator + Meltano details (emitted by the backend) |

## Local development

`docker compose up -d ingestion` starts `dagster dev` (webserver + daemon in one
process) on <http://localhost:3001>. Like prod, dev stores run/event/schedule
history in Postgres (the dedicated `dagster` schema, which lives in the `pgdata`
volume), so run history survives container resets and `docker compose down`. The
entrypoint runs `scripts/prepare_dagster_db.py` and drops a Postgres
`dagster.yaml` into `DAGSTER_HOME`; if the DB isn't reachable it falls back to
ephemeral SQLite (history not persisted). To run a batch immediately without
waiting for the schedule, trigger `discovery_job` (the sensors take it from
there) or `org_ingestion_job` from the UI's Launchpad, or run the CLI directly:

```bash
docker compose exec ingestion python -m app.ingestion.cli run
# time-based backfill (re-pull history since a date; dedupe absorbs overlap)
docker compose exec ingestion python -m app.ingestion.cli run --start-date 2026-01-01
```

## Production

The ECS service runs `dagster-daemon` + `dagster-webserver` from the same image
as the API (`infrastructure/docker/backend.prod.Dockerfile`, command
`dagster-service`). The UI is published at `https://dagster.<zone>` via the
shared ALB. Note: Dagster OSS has no built-in auth — treat the URL as sensitive
and restrict access at the network layer in a follow-up.
