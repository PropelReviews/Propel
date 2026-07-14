# Metric configuration system

Propel computes metrics from declarative YAML configs that compile to dbt models.
L1 standard metrics (`propel.*`) and future L2 org metrics share one format.

> Status: **M1 + M2 landed.** Validator + calendar-grain codegen for
> count / interval / percentile. Ratio / rolling windows (M3) and org MetricSets
> (M4) are next. Authoring UI (M5) is out of scope.

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
uv run pytest -v                       # schema, invalid fixtures, semantic matrix
```

CI also asserts: JSON Schema meta-validity, catalog self-check, an invalid-fixture
corpus (`tests/fixtures/invalid/`), compile determinism, and that every compilable
active metric is present in `models/metrics/generated/` and unioned into
`fct_metric_values`.

Validation passes: **structural** (JSON Schema) → **semantic** (entity catalog /
roles / ops) → **graph** (`extends` / operand refs / no derived-of-derived).

## Compilation (M2)

Active, non-derived metrics with calendar `time.grains` compile to:

- `transformation/dbt/models/metrics/generated/metric_propel_*.sql`
- `transformation/dbt/models/metrics/generated/fct_metric_values.sql` (union)

Durations are stored in **seconds**. Org-total dimension slots use `''` (empty
string) so incremental `unique_key` matching works under Postgres; treat `''` as
org total at serve time.

Generated SQL for `propel.*` is **committed**. CI fails if configs and SQL drift.

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
