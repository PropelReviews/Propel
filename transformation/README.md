# Transformation

dbt project for Propel — open, readable SQL that turns raw engineering events into metrics.

## Stack

- **Transformations:** dbt (Data Build Tool)
- **Database:** Postgres (populated by Meltano in the backend)

## Purpose

Every metric Propel surfaces is defined here as dbt models. This is the transparency layer: if you want to know how a number was calculated, trace it from the dashboard to the SQL in this directory.

Example metrics:

- Deployment frequency — published GitHub Releases
- Cycle time (PR open to merge) — DORA lead-time proxy
- Throughput — PR merge activity
- Review latency (time to first review)
- Change-failure proxy (revert-titled merges)
- Tooling activity signals

## Directory layout

```
transformation/
└── dbt/                                    # dbt project root
    ├── dbt_project.yml
    ├── profiles.yml                        # postgres profile, DBT_* env vars
    ├── .sqlfluff                           # SQL lint rules (postgres dialect, jinja templater)
    ├── ci/
    │   ├── fixture_raw_record.sql          # minimal raw_record + sample PRs/reviews for CI
    │   └── smoke_check.sql                 # asserts mart output matches the fixture
    └── models/
        ├── sources.yml                     # public.raw_record (+ github/linear source aliases)
        ├── staging/
        │   ├── stg_github_pull_requests.sql
        │   ├── stg_github_reviews.sql
        │   ├── stg_github_issues.sql
        │   └── stg_linear_issues.sql
        └── marts/
            ├── fct_deployment_frequency_daily.sql  # GitHub Releases
            ├── fct_pr_activity_daily.sql           # PR throughput
            ├── fct_pr_cycle_time_daily.sql         # lead-time proxy
            ├── fct_review_latency_daily.sql        # time to first review
            ├── fct_change_failure_daily.sql        # CFR proxy via reverts
            ├── fct_tickets.sql
            └── schema.yml
```

Models land in the `analytics` Postgres schema (raw landing tables stay in `public`). The `analytics` schema is dbt-owned — like Dagster's `dagster` schema, it is not managed by Alembic.

Marts set `REPLICA IDENTITY FULL` via pre/post-hooks so incremental `delete+insert` works when a Postgres publication publishes deletes (PostHog warehouse CDC). The warehouse publication itself is scoped to `public` only.

## Running

Dagster owns scheduled execution: every successful per-org ingestion run triggers a tenant-partitioned `dbt build --vars '{tenant_id: ...}'` (see `orchestration/propel_orchestration/analytics.py`). The incremental marts only recompute that tenant's rows.

Manual runs from the ingestion container (dbt is installed in the Dagster venv and the project is mounted at `/transformation`):

```bash
# Full rebuild of every tenant
docker compose exec ingestion dbt build --full-refresh \
  --project-dir /transformation/dbt --profiles-dir /transformation/dbt

# One tenant only
docker compose exec ingestion dbt build \
  --vars '{tenant_id: <uuid>}' \
  --project-dir /transformation/dbt --profiles-dir /transformation/dbt
```

Connection credentials come from `DBT_HOST` / `DBT_PORT` / `DBT_USER` / `DBT_PASSWORD` / `DBT_DBNAME` env vars (derived from `DATABASE_URL` automatically inside the Dagster service; defaults match local docker compose).

## Linting and CI

SQL style is enforced with [sqlfluff](https://sqlfluff.com) (config in `dbt/.sqlfluff`):

```bash
cd transformation/dbt
uvx --from "sqlfluff>=3,<4" sqlfluff lint models   # check
uvx --from "sqlfluff>=3,<4" sqlfluff fix models    # auto-fix
```

The `dbt checks` job in `.github/workflows/ci.yml` gates every PR:

1. `sqlfluff lint models` — SQL style.
2. `dbt parse` — project/ref validity.
3. Load `ci/fixture_raw_record.sql` into a throwaway Postgres (sample PR payloads).
4. `dbt build --full-refresh` then a tenant-scoped incremental `dbt build` — models execute and schema tests pass on both paths Dagster uses.
5. `ci/smoke_check.sql` — mart rows match the expected aggregates (including dedup of re-fetched PRs).

## Related

- [Backend](../backend/README.md) — Meltano extraction into Postgres
- [Frontend](../frontend/README.md) — dashboard that displays these metrics
