# propel-metrics

Declarative metric configuration for Propel: validate Metric / MetricSet /
DimensionMapping YAML against the entity catalog, resolve to a `CompiledPlan`
IR, and compile active metrics to dbt models that populate
`analytics.fct_metric_values`.

## Install

```bash
cd transformation/propel_metrics
uv sync --extra dev
```

## CLI

```bash
# Validate shipped configs (and any extra paths)
uv run propel-metrics validate
uv run propel-metrics validate --strict   # warnings → errors

# Compile propel.* metrics into transformation/dbt/models/metrics/generated/
uv run propel-metrics compile

# Fail if generated SQL drifts from configs, or inventory is incomplete (CI)
uv run propel-metrics compile --check

# Full local CI gate (validate --strict + compile --check + inventory)
uv run propel-metrics ci
uv run pytest -v
```

CI (`.github/workflows/ci.yml` job **Metric config checks**) runs lockfile check,
ruff, pytest (including `tests/fixtures/invalid/`, IR/expr/property tests), and
`propel-metrics ci`.

## Layout

| Path | Purpose |
|---|---|
| `propel_metrics/schema/` | JSON Schema for Metric, MetricSet, DimensionMapping, catalog |
| `propel_metrics/catalog/entities.yaml` | L0 entity/field contract |
| `propel_metrics/configs/propel/` | Shipped standard metric definitions |
| `propel_metrics/validate/` | Structural → semantic → graph validation |
| `propel_metrics/resolve/` | Flatten `extends`, content-hash resolved defs |
| `propel_metrics/ir/` | `CompiledPlan` IR (resolve → codegen) |
| `propel_metrics/expr/` | Formula tokenizer / parser / SQL emit |
| `propel_metrics/codegen/` | Emit dbt SQL (simple, ratio, formula, windows) |

See [docs/metrics/config-system.md](../../docs/metrics/config-system.md) for the
design summary.
