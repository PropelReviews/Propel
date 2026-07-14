# propel-metrics

Declarative metric configuration for Propel: validate Metric / MetricSet /
DimensionMapping YAML against the entity catalog, resolve to a `CompiledPlan`
IR (including org MetricSets, params, and mappings), and compile to dbt models
that populate `analytics.fct_metric_values`.

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
uv run propel-metrics compile --check

# Full local CI gate
uv run propel-metrics ci
uv run pytest -v

# M4 definition store (JSON dogfood; hosted uses Postgres + API)
uv run propel-metrics import-system --store .propel-store.json
uv run propel-metrics pull --org acme --store .propel-store.json ./metrics-out
uv run propel-metrics push --org acme --store .propel-store.json ./metrics-out --activate
uv run propel-metrics repin --org acme --id acme.child --store .propel-store.json
uv run propel-metrics archive --org acme --id acme.old --store .propel-store.json
```

CI (`.github/workflows/ci.yml` job **Metric config checks**) runs lockfile check,
ruff, pytest, and `propel-metrics ci`.

## Layout

| Path | Purpose |
|---|---|
| `propel_metrics/schema/` | JSON Schema for Metric, MetricSet, DimensionMapping, catalog |
| `propel_metrics/catalog/entities.yaml` | L0 entity/field contract |
| `propel_metrics/configs/propel/` | Shipped standard metric definitions |
| `propel_metrics/validate/` | Structural → semantic → graph validation |
| `propel_metrics/resolve/` | Extends, org resolve, params, lifecycle |
| `propel_metrics/store/` | DefinitionStore protocol + memory/JSON backends |
| `propel_metrics/sync/` | push/pull + lockfile |
| `propel_metrics/ir/` | `CompiledPlan` IR (resolve → codegen) |
| `propel_metrics/expr/` | Formula tokenizer / parser / SQL emit |
| `propel_metrics/codegen/` | Emit dbt SQL (simple, ratio, formula, windows, shared) |

See [docs/metrics/config-system.md](../../docs/metrics/config-system.md) and
[docs/metrics/definition-store.md](../../docs/metrics/definition-store.md).
