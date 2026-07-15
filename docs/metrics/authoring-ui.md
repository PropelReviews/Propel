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

## Client validation

- Generated types: `npm run metrics:gen-types` (from `transformation/propel_metrics/.../schema`)
- Tier-1: ajv JSON Schema + cheap semantic mirrors (`schema/client-validate.ts`)
- Tier-2: debounced `POST …/metric-definitions:validate` (server wins)

## Formula parser

TypeScript port of `propel_metrics.expr.parse` with a shared corpus at
`transformation/propel_metrics/tests/fixtures/formula_corpus.json`.

## Preview (`POST …/metric-definitions:preview`)

The builder’s **Run preview** posts the current document YAML. The API:

1. Validates YAML
2. Builds a `CompiledPlan` (including catalog entity dimensions such as
   `author_id`, and org DimensionMappings for virtual dims like `team`)
3. Rewrites dbt Jinja → executable SQL (coarsest grain, 90d window, row limit)
4. Executes against the warehouse when L0 relations exist; otherwise returns
   **dry-run SQL** with a diagnostic

| Warehouse state | Response |
|---|---|
| `analytics.pull_request` (or `public.…`) present | `executed: true` + sample rows |
| L0 entity tables missing | `executed: false`, diagnostic about dry-run; SQL still returned |
| Compile / dimension errors | JSON `400` with `code: PREVIEW_COMPILE_FAILED` (never plain-text 500) |

Preview needs the **canonical** L0 models (`pull_request`, `release`, …), not
only staging views like `stg_github_pull_requests`. Build them via dbt (see
[transformation/README.md](../../transformation/README.md)):

```bash
docker compose exec ingestion dbt build --select pull_request \
  --project-dir /transformation/dbt --profiles-dir /transformation/dbt
```

IC-visibility metrics filter person-dimension rows to the caller’s linked
GitHub identity when execution succeeds.

Frontend dependency: the SPA parses YAML with the `yaml` npm package
(`frontend/package.json`). After pulling M5 changes, run `npm install` in
`frontend/` if Vite reports `Failed to resolve import "yaml"`.

