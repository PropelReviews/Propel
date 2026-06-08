# Propel Orchestration (Dagster)

Dagster is the scheduler for Propel ingestion. It runs as a long-running ECS
service (daemon + webserver) that triggers ingestion on an hourly schedule. The
extraction pipeline itself (Meltano taps + `target-propel`) lives in
[`../backend`](../backend) and is unchanged.

`ingestion_job` is a granular DAG — one op per GitHub resource — and runs **once
per org**: the schedule lists active installations and fans out a separate run
for each, so a slow or failing org is isolated to its own run/UI entry.

```
discover_orgs ─┬─> get_org_members ──> get_user_profiles ─┐
               ├─> get_commits ───────────────────────────┤
               ├─> get_pull_requests ─────────────────────┤
               ├─> get_issues ────────────────────────────┤
               └─> get_copilot_usage ─────────────────────┴─> flush_logs
```

- **One run per org.** `ingestion_schedule` queries active orgs each hour and
  emits a `RunRequest` per org, tagged `propel/account_id` + `propel/org`. Each
  op reads the tag and calls `orchestrator.run_all(account_id=..., job_name=...)`
  scoped to that org. Launching the job manually from the Launchpad with no tag
  processes every active org in one run.
- `get_user_profiles` runs after `get_org_members` (it targets the discovered
  member logins); the repo-activity and Copilot ops fan out from discovery.
  `flush_logs` fans in last to drain the OTLP batch handler before exit.
- **Assets.** Each resource op emits an `AssetMaterialization` per
  `ingestion_run` (asset keys `github/commits`, `github/issues`, …) with
  `records_pulled` / `datapoints_written` / org metadata, so the Assets catalog
  reflects what landed. (We use ops, not software-defined assets, because the
  work is imperative extraction; the materialization events give the catalog +
  lineage without modeling each resource as an SDA.)

```
orchestration/
  pyproject.toml                      deps: dagster + backend runtime deps
  dagster.yaml                        prod Postgres storage (dedicated schema)
  workspace.yaml                      code location -> propel_orchestration.definitions
  scripts/prepare_dagster_db.py       creates the `dagster` schema, prints DAGSTER_PG_URL
  propel_orchestration/
    definitions.py                    Definitions(jobs, schedules)
    jobs.py                           ingestion_job + hourly ingestion_schedule
    logging.py                        OTLP -> PostHog as service.name=propel-ingestion
```

## How it runs

- The webserver and daemon load `propel_orchestration.definitions`. The op
  imports the backend `app` package, which is made importable via `PYTHONPATH`
  (not installed as a wheel) so the same source serves both projects.
- `ingestion_schedule` auto-starts (`DefaultScheduleStatus.RUNNING`) and fires
  `0 * * * *` (UTC), emitting one run per active org each tick.
- Dagster's run/event/schedule storage shares the app's Postgres but lives in a
  dedicated `dagster` schema (see `scripts/prepare_dagster_db.py`) so its own
  `alembic_version` never collides with the app's migrations.

## Observability

All logs ship to PostHog as `service.name = propel-ingestion`. Useful events:

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
waiting for the schedule, trigger `ingestion_job` from the UI's Launchpad, or run
the CLI directly:

```bash
docker compose exec ingestion python -m app.ingestion.cli run
```

## Production

The ECS service runs `dagster-daemon` + `dagster-webserver` from the same image
as the API (`infrastructure/docker/backend.prod.Dockerfile`, command
`dagster-service`). The UI is published at `https://dagster.<zone>` via the
shared ALB. Note: Dagster OSS has no built-in auth — treat the URL as sensitive
and restrict access at the network layer in a follow-up.
