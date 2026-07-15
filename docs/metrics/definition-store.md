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

- `GET .../metric-definitions` — enriched catalog rows (enrollment + drafts/broken;
  `?referencable=1` for operand pickers; optional `entity=`)
- `GET .../metric-catalog` — entity catalog + org virtual dimensions (`person` field metadata)
- `GET .../metric-definitions/detail?metric_id=`
- `GET .../metric-definitions/versions?metric_id=` — version history
- `GET .../metric-definitions/sql?metric_id=` — generated SQL artifact
- `POST .../metric-definitions:diff` — resolved-JSON structural diff
- `POST .../metric-definitions:validate` — pure, structured errors
- `POST .../metric-definitions` — create draft
- `PUT .../metric-definitions/draft` — autosave with optimistic
  `expected_version` / `expected_revision` (409 on conflict)
- `POST .../metric-definitions:classify` — semantic vs revision dry-run
- `POST .../metric-definitions:preview` — authoring preview (SQL + optional
  warehouse execution; see [authoring-ui.md](./authoring-ui.md#preview-post-metric-definitionspreview))
- `POST .../metric-definitions:activate?metric_id=`
- `POST .../metric-definitions:repin?metric_id=`
- `POST .../metric-definitions:archive?metric_id=`
- `GET/PUT .../metric-set`
- `GET .../dimension-mappings` — list mappings
- `GET/PUT .../dimension-mappings` (detail via `?mapping_id=` on GET detail path)
- `GET .../metric-health` — broken metrics, notices, recent compile runs
- `GET .../metric-compile-runs`

## Compile source

| `METRICS_COMPILE_SOURCE` | Behavior |
|---|---|
| `files` | CI / `propel-metrics compile` owns committed SQL; dirty rows are still recorded |
| `db` (**default**) | Resolve orgs from `metric_definitions`, emit shared-hash models |

Activation / MetricSet / mapping writes mark `metric_compile_dirty`. The Dagster
sensor `metrics_compile_dirty_sensor` launches `metrics_compile_build`, which
claims a single-flight `metric_compile_runs` row and drains the dirty set.
Hourly schedule runs a full resolve backstop.

### Generated SQL inventory

Two kinds of files land under `transformation/dbt/models/metrics/generated/`:

| Kind | Pattern | Committed? |
|---|---|---|
| File-pipeline (CI) | `metric_propel_*.sql`, `fct_metric_values.sql`, `schema.yml` | **Yes** — `propel-metrics compile --check` |
| Store-pipeline (runtime) | `metric_<slug>__<hash12>.sql`, `metric_enrollment.sql` | **No** — gitignored; drift check ignores them |

A local `db` compile writing into the bind-mounted repo can leave hash-suffixed
artifacts beside the committed inventory. They are safe to delete; do not commit
them. `propel-metrics compile --check` / `check_drift` only require the
unversioned `metric_propel_*.sql` set to match a fresh file compile.

Parity gate before relying on `db` in a new environment:

```bash
uv run propel-metrics import-system --store .propel-store.json
uv run propel-metrics resolve-parity --org acme --store .propel-store.json
```

Override with `METRICS_COMPILE_SOURCE=files` to force the file pipeline.

## Serving swap

`fct_metric_values` is a **table**. After rebuilding a metric model, the compile
job runs `swap_metric_values` (see `transformation/dbt/macros/swap_metric_values.sql`)
so readers never see mixed `definition_version` rows for a metric.

