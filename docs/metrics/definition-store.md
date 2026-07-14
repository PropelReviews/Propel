# Metric definition store (M4)

Propel stores Metric / MetricSet / DimensionMapping documents in Postgres and
resolves them per org into `CompiledPlan` IRs that compile to dbt models.

## Naming

| Concept | Value |
|---|---|
| Store `org_id` | Tenant **slug**, or `__system` for `propel.*` |
| Warehouse tenant key | `tenant_id` UUID |
| API paths | `/api/v1/tenants/{tenant_id}/...` (UUID) |
| Tenancy enforcement | Application-layer only (**no RLS**) |

## Tables

- `metric_definitions` — versioned authored YAML + resolved JSON/hash for Metrics;
  also holds MetricSet (`metric_id='metric_set'`) and DimensionMapping rows
- `org_metric_enrollment` — resolved enrollment (pure function of MetricSet + defs)
- `definition_notices` — e.g. `parent_version_available` after parent bumps
- `metric_compile_dirty` / `metric_compile_runs` — dirty-set compile orchestration

Partial unique index: at most one `active|broken` version per `(org_id, metric_id)`.

## Version vs revision

- **Non-semantic** edits (`metadata.name/description/tags/owner/advanced`,
  `spec.display`) bump `revision` in place.
- **Semantic** edits create version `N+1` as `draft`; activation deprecates the
  prior active row in one transaction.

## Content hash

`content_hash = sha256(canonical CompiledPlan JSON)`. Identical hashes across
orgs share one generated dbt model (`metric_<slug>__<hash12>.sql`).

File-pipeline CI still embeds the short semantic-spec hash as
`definition_version` in committed SQL. Store-backed compiles emit the integer
semantic `version` as `definition_version` and use `content_hash` for dedupe.

## Resolve

```
MetricSet → standard ids (default_on|explicit) + custom ids
  → bind MetricSet.params into declared params
  → flatten extends via parent_pin
  → rewrite DimensionMappings into MappedDim
  → build CompiledPlan + enroll
```

Operand refs resolve in the **caller org’s** param context.

## CLI (JSON store dogfood)

```bash
cd transformation/propel_metrics
uv run propel-metrics import-system --store .propel-store.json
uv run propel-metrics pull --org acme --store .propel-store.json ./metrics-out
uv run propel-metrics push --org acme --store .propel-store.json ./metrics-out --activate
uv run propel-metrics repin --org acme --id acme.child --store .propel-store.json
uv run propel-metrics archive --org acme --id acme.old --store .propel-store.json
```

Hosted production uses the FastAPI APIs + Alembic tables; the JSON store is for
local push/pull round-trips and tests.

## API (admin writes)

Permission `metrics:manage` (admin default) for writes; `metrics:read` for reads.

- `GET .../metric-definitions` — resolved enrollment summary
- `GET .../metric-definitions/detail?metric_id=`
- `POST .../metric-definitions:validate` — pure, structured errors
- `POST .../metric-definitions` — create draft
- `POST .../metric-definitions:activate?metric_id=`
- `POST .../metric-definitions:repin?metric_id=`
- `POST .../metric-definitions:archive?metric_id=`
- `GET/PUT .../metric-set`
- `GET/PUT .../dimension-mappings`
- `GET .../metric-compile-runs`

## Compile source

| `METRICS_COMPILE_SOURCE` | Behavior |
|---|---|
| `files` (default) | CI / `propel-metrics compile` owns committed SQL |
| `db` | Resolve orgs from `metric_definitions`, emit shared-hash models |

Parity gate:

```bash
uv run propel-metrics import-system --store .propel-store.json
uv run propel-metrics resolve-parity --org acme --store .propel-store.json
```

Activation dirties content hashes and enqueues a single-flight compile run
(`metric_compile_runs`). Dagster job `metrics_compile_build` (hourly schedule,
stopped by default) drains the dirty set when `METRICS_COMPILE_SOURCE=db`.

## Serving swap

`fct_metric_values` is a **table**. After rebuilding a metric model, the compile
job runs `swap_metric_values` (see `transformation/dbt/macros/swap_metric_values.sql`)
so readers never see mixed `definition_version` rows for a metric.

