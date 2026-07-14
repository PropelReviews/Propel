# Metric configuration system

Propel computes metrics from declarative YAML configs that compile to dbt models.
L1 standard metrics (`propel.*`) and future L2 org metrics share one format.

> Status: **M1 + M2 + M3 landed.** Validator, IR (`CompiledPlan`), calendar-grain
> and rolling-window codegen for count / interval / percentile / **ratio** /
> **formula**. Org MetricSets + definition store (M4) and authoring UI (M5) are next.

## Layers

| Layer | What | Where |
|---|---|---|
| L0 — entities | Canonical rows (`pull_request`, `release`, …) | `transformation/dbt/models/canonical/` + catalog |
| L1 — standard metrics | Shipped Metric YAML in the `propel` namespace | `transformation/propel_metrics/propel_metrics/configs/propel/` |
| L2 — org metrics | Org-defined configs (later) | MetricSet + org namespace |

## Package

`transformation/propel_metrics` (`propel-metrics` CLI):

```bash
cd transformation/propel_metrics
uv sync --extra dev
uv run propel-metrics validate --strict
uv run propel-metrics compile          # writes dbt SQL
uv run propel-metrics ci               # validate --strict + compile --check + inventory
uv run pytest -v                       # schema, invalid fixtures, IR/expr/property suite
```

CI also asserts: JSON Schema meta-validity, catalog self-check, an invalid-fixture
corpus (`tests/fixtures/invalid/`), compile determinism, and that every compilable
active metric is present in `models/metrics/generated/` and unioned into
`fct_metric_values`.

Validation passes: **structural** (JSON Schema) → **semantic** (entity catalog /
roles / ops / formula syntax) → **graph** (`extends` / operand refs / no
derived-of-derived).

## Compilation pipeline (M3)

```
YAML ─► validate ─► resolve (extends) ─► CompiledPlan (IR) ─► SQL codegen ─► dbt
```

Active metrics with calendar `time.grains` and/or rolling `time.windows` compile
when the measure is a simple aggregate **or** a derived `ratio` / `formula`:

- Per-metric models: `transformation/dbt/models/metrics/generated/metric_propel_*.sql`
  (`materialized='table'`)
- Serving union: `fct_metric_values.sql` (`materialized='view'`)
- Shared spine: `models/metrics/dim_step_spine.sql` (`history_days` var, default 730)

**Ratio** uses the denominator bucket universe (`LEFT JOIN` numerator).  
**Formula** uses the union of input buckets; `/` emits `nullif` (NULL on ÷0).  
**Windows** spine-join unaggregated rows over `(end - N days, end]` with grain
label `rolling_{N}d`.

Durations are stored in **seconds**. Org-total dimension slots use `''` (empty
string); treat `''` as org total at serve time. `value` may be NULL for
ratio/formula divide-by-zero.

Generated SQL for `propel.*` is **committed**. CI fails if configs and SQL drift.

Shipped M3 dogfood: `propel.change_failure_rate` (ratio),
`propel.cycle_time_trailing_30d` (30d rolling window). `propel.mttr` stays draft
until an incident L0 entity exists.

## Dual-run with legacy marts

Hand-written `fct_*_daily` marts and the FastAPI metrics endpoints remain the
serving path. `fct_metric_values` dual-runs until the API cutover. Do not delete
legacy DORA marts until that cutover.

## Visibility (push-to-pull)

Every Metric declares `visibility: ic | team | org`. Flow metrics that describe
people default to `ic`. Dimension mappings (M4) never broaden visibility;
`extends` children may not escalate visibility above their parent.

## Tenancy naming

Configs and docs say “org”; the warehouse column and catalog tenant key are
`tenant_id` (UUID). MetricSet `metadata.org` (M4) is the tenant **slug**.
