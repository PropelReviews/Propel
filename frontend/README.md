# Frontend

React dashboard for Propel — the UI layer for inspecting engineering metrics.

## Stack

- **Framework:** React
- **Build tool:** Vite
- **Language:** TypeScript

## Purpose

The frontend presents metrics surfaced by the backend API: cycle time, throughput, review patterns, and tooling activity. Every number on the dashboard should be traceable back to the dbt models that produce it.

## Setup

```bash
cd frontend
npm install
npm run dev
```

The dev server listens on port `5173` by default.

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server |
| `npm run build` | Type-check and build for production |
| `npm run preview` | Preview production build locally |

## Related

- [Backend](../backend/README.md) — FastAPI API this dashboard consumes
- [Transformation](../transformation/README.md) — dbt models that define the metrics
