# propel-metrics

Declarative metric configuration for Propel: validate Metric / MetricSet /
DimensionMapping YAML against the entity catalog, and compile active metrics to
dbt models that populate `analytics.fct_metric_values`.

## Install

```bash
cd transformation/propel_metrics
uv sync --extra dev
```

## CLI

```bash
# Validate shipped configs (and any extra paths)
uv run propel-metrics validate

# Compile propel.* metrics into transformation/dbt/models/metrics/generated/
uv run propel-metrics compile

# Fail if generated SQL drifts from configs (CI)
uv run propel-metrics compile --check
```

## Layout

| Path | Purpose |
|---|---|
| `propel_metrics/schema/` | JSON Schema for Metric, MetricSet, DimensionMapping, catalog |
| `propel_metrics/catalog/entities.yaml` | L0 entity/field contract |
| `propel_metrics/configs/propel/` | Shipped standard metric definitions |
| `propel_metrics/validate/` | Structural → semantic → graph validation |
| `propel_metrics/resolve/` | Flatten `extends`, content-hash resolved defs |
| `propel_metrics/codegen/` | Emit dbt SQL |

See [docs/metrics/config-system.md](../../docs/metrics/config-system.md) for the
design summary.
