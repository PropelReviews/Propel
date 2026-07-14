# Metric authoring UI (M5)

The web UI is a **structured editor over `propel/v1` documents**. Every save
writes the same YAML the push/pull CLI and validator understand. There is no
UI-only semantic state.

## Routes

| Path | Purpose |
|---|---|
| `/metrics` | Catalog (enrollment + drafts/broken) |
| `/metrics/new` | Builder (create / variant via `?extends=`) |
| `/metrics/:id` | Detail — Overview / Definition / Versions |
| `/metrics/:id/edit` | Builder (edit → draft); forks `propel.*` |
| `/settings/metric-set` | MetricSet YAML (enable/disable + params) |
| `/settings/dimension-mappings` | Virtual dimension list |
| `/settings/metric-health` | Compile runs, broken, parent notices |

## Permissions

- `metrics:read` — browse catalog, detail, preview, health
- `metrics:manage` — drafts, activate, MetricSet, mappings, repin

## Principles productized

1. Form state = document (JSON-path reducer)
2. Round-trip CI for non-advanced `propel.*` configs (`roundtrip.corpus.test.ts`)
3. Advanced / raw SQL → read-only banner
4. Progressive disclosure (simple path first; derived cards gated)
5. View as YAML + generated SQL / preview SQL
6. Visibility copy + person-dimension nudge

## API companions

See [definition-store.md](./definition-store.md) for catalog, draft PUT,
classify, diff, preview, and health endpoints.
