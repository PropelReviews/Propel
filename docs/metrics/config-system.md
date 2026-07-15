# Metric configuration system

Propel computes metrics from declarative YAML configs that compile to dbt models.
L1 standard metrics (`propel.*`) and L2 org metrics share one format.

> Status: **M1–M5 authoring UI landed (iterative).** Validator, IR, codegen,
> org MetricSets / definition store (M4), plus catalog/builder/preview/variants
> UI (M5). See [authoring-ui.md](./authoring-ui.md).

## Layers

| Layer | What | Where |
|---|---|---|
| L0 — entities | Canonical rows (`pull_request`, `release`, …) | `transformation/dbt/models/canonical/` + catalog |
| L1 — standard metrics | Shipped Metric YAML in the `propel` namespace | `transformation/propel_metrics/.../configs/propel/` + `__system` store |
| L2 — org metrics | Org MetricSet + custom defs / mappings | Postgres `metric_definitions` (slug = `org_id`) |

## Package

`transformation/propel_metrics` (`propel-metrics` CLI):

```bash
cd transformation/propel_metrics
uv sync --extra dev
uv run propel-metrics validate --strict
uv run propel-metrics compile          # file pipeline → dbt SQL
uv run propel-metrics ci
uv run propel-metrics import-system    # seed JSON/DB store from propel.* YAML
uv run propel-metrics pull|push|repin|archive
uv run pytest -v
```

Validation passes: **structural** → **semantic** → **graph**.

## Compilation pipeline

```
YAML/DB ─► validate ─► resolve(org) ─► CompiledPlan (IR) ─► content_hash ─► SQL
```

- File pipeline (CI default): active `propel.*` → committed
  `models/metrics/generated/metric_propel_*.sql`
- Store pipeline (M4): enrollment by content_hash → shared
  `metric_<slug>__<hash12>.sql` + `metric_enrollment.sql` (runtime; gitignored)
- Serving: `fct_metric_values` **table** with per-metric swap
  (`macros/swap_metric_values.sql`)

**Dimensions.** Catalog entity fields with `role: dimension` (e.g. `repo`,
`author_id`, `state`) compile as native `dim_*` columns. Virtual dims such as
`team` still require an org DimensionMapping. Stable serving columns for the
file-pipeline union remain `dim_repo` / `dim_team`; extra catalog dims are
appended on plans that select them (preview / org models).

See [definition-store.md](./definition-store.md) for store schema, pins, API,
preview, and push/pull.

## Dual-run with legacy marts

Hand-written `fct_*_daily` marts and the FastAPI *values* endpoints remain the
dashboard serving path. Definition APIs are live; values cutover is separate.

## Visibility (push-to-pull)

Every Metric declares `visibility: ic | team | org`. Dimension mappings never
broaden visibility; `extends` children may not escalate above their parent.

## Tenancy naming

Configs and docs say “org”; the warehouse column is `tenant_id` (UUID).
MetricSet `metadata.org` / store `org_id` is the tenant **slug**. Tenancy is
enforced in application code (no Postgres RLS on definition tables).
