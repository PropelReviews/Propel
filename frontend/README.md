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

| Command           | Description                         |
| ----------------- | ----------------------------------- |
| `npm run dev`     | Start Vite dev server               |
| `npm run build`   | Type-check and build for production |
| `npm run preview` | Preview production build locally    |

## Landing page preview

During normal dev, the landing Vite app runs as `frontend-landing` on port 5174
(see `infrastructure/docker/README.md`).

To preview the prebuilt static artifact in `dist-landing/` (`landing.html` +
assets), use the on-demand nginx service:

```bash
docker compose --profile landing up frontend-landing-static   # http://localhost:8080 (LANDING_PORT)
```

It is behind the `landing` Compose profile, so it does not start with the
default `docker compose up` stack.

## Analytics

Product analytics run through PostHog. Autocapture records every click/pageview,
global super properties (`app_environment`, `app_version`, `git_sha`) tag every
event, and the shared `Button` emits structured `data-ph-capture-attribute-*`
metadata. See [docs/frontend/analytics.md](../docs/frontend/analytics.md) for the
full event taxonomy.

Optional build-time env vars (all default sensibly):

| Var                                      | Purpose                                                                  |
| ---------------------------------------- | ------------------------------------------------------------------------ |
| `VITE_POSTHOG_KEY` / `VITE_POSTHOG_HOST` | Enable PostHog and point it at a host                                    |
| `VITE_APP_ENV`                           | Environment label (defaults to Vite mode)                                |
| `VITE_APP_VERSION`                       | App version (defaults to `package.json` version)                         |
| `VITE_GIT_SHA`                           | Build commit SHA (defaults to `dev`)                                     |
| `VITE_API_URL`                           | Backend API base URL (defaults to `http://localhost:8000`)               |
| `VITE_AUTH_ENABLED`                      | Fallback to show auth when PostHog is disabled (default off)             |
| `VITE_CHART_DEMO_ENABLED`                | Fallback to show the chart demo when PostHog is disabled (default off)   |
| `VITE_LANDING_BLOG_ENABLED`              | Fallback to show the landing blog when PostHog is disabled (default off) |
| `VITE_LANDING_CAREERS_ENABLED`           | Fallback to show landing careers when PostHog is disabled (default off)  |

PostHog error tracking and session replay are enabled in code when a key is set.
Session replay must also be turned on in your PostHog project settings. Production
deploys upload source maps when `POSTHOG_PERSONAL_API_KEY` and `POSTHOG_PROJECT_ID`
are set in the build environment — see [analytics docs](../docs/frontend/analytics.md).

## Auth (sign up / sign in)

Email/password auth wired to the backend `/api/v1/auth` endpoints.

- **Routes:** `/signin` and `/signup` (the landing page links to them when auth is enabled).
- **Feature flag:** the entire auth surface is gated behind the PostHog feature flag **`signup-signin`**. Create and enable it in PostHog to expose auth. When PostHog runs without a key (keyless self-host), set `VITE_AUTH_ENABLED=true` to enable it instead.
- **Session:** the JWT is stored in `localStorage` (`propel_token`) and validated against `/api/v1/auth/me` on load.
- **Backend:** must be running with migrations applied — `cd backend && alembic upgrade head`.

See [docs/frontend/analytics.md](../docs/frontend/analytics.md) for the auth events and the `signup-signin` flag.

## Chart library demo

A visual gallery of the chart design library lives at `/dev/charts` (metric
cards, line/bar/area widgets, bare primitives, and a date-range + granularity
picker that drives every chart on the page).

- **Feature flag:** gated behind the PostHog feature flag **`chart-demo`**.
  Enable it in PostHog to expose the route and the homepage link. When PostHog
  runs without a key (keyless self-host), set `VITE_CHART_DEMO_ENABLED=true`
  instead.

## Landing blog & careers

The marketing landing build (`npm run dev:landing` / `npm run build:landing`)
includes optional `/blog` and `/careers` routes:

- **Blog:** Markdown posts in [`content/blog/`](content/blog/) (YAML frontmatter
  - body). See that folder's README for the post format. Gated by PostHog flag
    **`landing-blog`** (env fallback `VITE_LANDING_BLOG_ENABLED`).
- **Careers:** Static page with a mailto to `sam@propel.ninja`. Gated by
  PostHog flag **`landing-careers`** (env fallback `VITE_LANDING_CAREERS_ENABLED`).

Both flags default **off**. Create them as boolean flags in PostHog to soft-launch.

## Related

- [Analytics taxonomy](../docs/frontend/analytics.md) — PostHog events & properties
- [Backend](../backend/README.md) — FastAPI API this dashboard consumes
- [Transformation](../transformation/README.md) — dbt models that define the metrics
