# Transformation

dbt project for Propel — open, readable SQL that turns raw engineering events into metrics.

## Stack

- **Transformations:** dbt (Data Build Tool)
- **Database:** Postgres (populated by Meltano in the backend)

## Purpose

Every metric Propel surfaces is defined here as dbt models. This is the transparency layer: if you want to know how a number was calculated, trace it from the dashboard to the SQL in this directory.

Example metrics:

- Cycle time (PR open to merge)
- Throughput (work shipped over time)
- Review patterns
- Tooling activity signals

## Directory layout

```
transformation/
└── dbt/                                    # dbt project root
    ├── dbt_project.yml
    ├── profiles.yml                        # postgres profile, DBT_* env vars
    └── models/
        ├── sources.yml                     # public.raw_record (lineage -> github/pull_requests asset)
        ├── staging/
        │   └── stg_github_pull_requests.sql
        └── marts/
            ├── fct_pr_activity_daily.sql   # incremental, delete+insert per tenant/day
            └── schema.yml
```

Models land in the `analytics` Postgres schema (raw landing tables stay in `public`). The `analytics` schema is dbt-owned — like Dagster's `dagster` schema, it is not managed by Alembic.

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

## Related

- [Backend](../backend/README.md) — Meltano extraction into Postgres
- [Frontend](../frontend/README.md) — dashboard that displays these metrics
