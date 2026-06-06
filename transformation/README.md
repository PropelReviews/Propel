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
└── dbt/            # dbt project root (models, macros, tests)
```

## Setup

Setup instructions coming soon. Once the dbt project is initialized:

```bash
cd transformation/dbt
dbt deps
dbt run
dbt test
```

## Related

- [Backend](../backend/README.md) — Meltano extraction into Postgres
- [Frontend](../frontend/README.md) — dashboard that displays these metrics
