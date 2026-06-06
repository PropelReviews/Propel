# Frontend

React dashboard for Propel — the UI layer for inspecting engineering metrics.

## Stack

- **Framework:** React
- **Build tool:** Vite
- **Language:** TypeScript

## Purpose

The frontend presents metrics surfaced by the backend API: cycle time, throughput, review patterns, and tooling activity. Every number on the dashboard should be traceable back to the dbt models that produce it.

## Setup

Setup instructions coming soon. Once the app is scaffolded, local development will run via:

```bash
npm install
npm run dev
```

The dev server listens on port `5173` by default.

## Related

- [Backend](../backend/README.md) — FastAPI API this dashboard consumes
- [Transformation](../transformation/README.md) — dbt models that define the metrics
