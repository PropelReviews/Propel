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

## Analytics

Product analytics run through PostHog. Autocapture records every click/pageview,
global super properties (`app_environment`, `app_version`, `git_sha`) tag every
event, and the shared `Button` emits structured `data-ph-capture-attribute-*`
metadata. See [docs/frontend/analytics.md](../docs/frontend/analytics.md) for the
full event taxonomy.

Optional build-time env vars (all default sensibly):

| Var | Purpose |
|---|---|
| `VITE_POSTHOG_KEY` / `VITE_POSTHOG_HOST` | Enable PostHog and point it at a host |
| `VITE_APP_ENV` | Environment label (defaults to Vite mode) |
| `VITE_APP_VERSION` | App version (defaults to `package.json` version) |
| `VITE_GIT_SHA` | Build commit SHA (defaults to `dev`) |
| `VITE_API_URL` | Backend API base URL (defaults to `http://localhost:8000`) |
| `VITE_AUTH_ENABLED` | Fallback to show auth when PostHog is disabled (default off) |

## Auth (sign up / sign in)

Email/password auth wired to the backend `/api/v1/auth` endpoints.

- **Routes:** `/signin` and `/signup` (the landing page links to them when auth is enabled).
- **Feature flag:** the entire auth surface is gated behind the PostHog feature flag **`signup-signin`**. Create and enable it in PostHog to expose auth. When PostHog runs without a key (keyless self-host), set `VITE_AUTH_ENABLED=true` to enable it instead.
- **Session:** the JWT is stored in `localStorage` (`propel_token`) and validated against `/api/v1/auth/me` on load.
- **Backend:** must be running with migrations applied — `cd backend && alembic upgrade head`.

See [docs/frontend/analytics.md](../docs/frontend/analytics.md) for the auth events and the `signup-signin` flag.

## Related

- [Analytics taxonomy](../docs/frontend/analytics.md) — PostHog events & properties
- [Backend](../backend/README.md) — FastAPI API this dashboard consumes
- [Transformation](../transformation/README.md) — dbt models that define the metrics
