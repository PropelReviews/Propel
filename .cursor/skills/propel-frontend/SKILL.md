---
name: propel-frontend
description: Conventions and commands for the Propel React frontend — dual app/landing builds, shadcn/Tailwind v4 patterns, auth flow, API client, Vitest unit/browser tests. Use when editing anything under frontend/, working with React components, charts, the landing page, or VITE_ env vars.
---

# Propel Frontend

React 19 + Vite + TypeScript (strict) + Tailwind v4 + shadcn/ui. All commands run from `frontend/`.

## Two builds, one `src/`

| | App (dashboard) | Landing (marketing) |
|---|---|---|
| Entry | `index.html` → `src/main.tsx` | `landing.html` → `src/landing-main.tsx` |
| Config | `vite.config.ts` | `vite.landing.config.ts` |
| Output | `dist/` | `dist-landing/` |
| Dev | `npm run dev` (:5173) | `npm run dev:landing` (:5174) |
| Build | `npm run build` | `npm run build:landing` |

Landing source is real React under `src/pages/landing/` — never edit `dist*/`. Landing has **no router and no `AuthProvider`** — don't import `useAuth()` there. (`docs/frontend/analytics.md` claims landing has no React source; that's stale.)

## Commands

```bash
npm run lint && npm run format:check && npm run typecheck && npm test
npm run format        # auto-fix (Prettier + tailwind class sorting)
npm run storybook     # :6006 (charts have stories)
```

CI also runs both builds. Vitest has two projects: `unit` (Node, `*.test.tsx`) and `browser` (Playwright Chromium, `*.browser.test.tsx`). Charts/Recharts need real DOM → write browser tests using `renderInDom`/`waitFor` from `src/test/render-browser.tsx`.

## Structure

- `src/routes.tsx` — React Router v7; auth pages and `/dev/charts` are gated by PostHog flags (`signup-signin`, `chart-demo`) with `VITE_AUTH_ENABLED` / `VITE_CHART_DEMO_ENABLED` env fallbacks. Default **off**.
- `src/lib/api.ts` — single fetch-based client. `API_BASE` from `VITE_API_URL` (default `http://localhost:8000`). `ApiError` class; `authedGet()` for bearer-token calls. Domain modules (e.g. `src/lib/ingestion.ts`) build on it. **No axios / React Query / Redux.**
- `src/providers/auth-provider.tsx` — React Context; JWT in `localStorage` (`propel_token`, `propel_user`); validated on boot via `GET /api/v1/auth/me`. Uses React 19 `<AuthContext value={...}>` syntax.
- Login posts `application/x-www-form-urlencoded` with field **`username`** (the email) — fastapi-users requirement.
- GitHub OAuth callback lands on `/auth/github/callback` with token in the URL fragment.
- Forms: react-hook-form + Zod (schemas in `src/lib/auth-schemas.ts`).
- Charts: barrel export at `src/components/charts/index.ts`; filters via `MetricFiltersProvider` context.

## UI conventions

- shadcn config in `components.json` (style `radix-nova`, lucide icons). Add primitives via the shadcn CLI into `src/components/ui/`.
- Tailwind v4 via Vite plugin — **no `tailwind.config.js`**; global CSS is `src/index.css`.
- Use `cn()` from `src/lib/utils.ts`; variants via CVA; `@/*` alias → `src/*`.
- Theme defaults to **dark** (next-themes). Use semantic tokens (`bg-background`, `text-muted-foreground`), never hardcoded colors.
- `Button` accepts `analyticsName` → PostHog capture attributes. Event taxonomy: `docs/frontend/analytics.md`.

## Env vars

Vite reads `.env` from the **repo root** (`envDir: ..`) and `frontend/`; local wins. Key vars: `VITE_API_URL` (app), `VITE_APP_URL`/`VITE_GITHUB_URL` (landing), `VITE_POSTHOG_KEY`/`VITE_POSTHOG_HOST` (falls back to `POSTHOG_TOKEN`/`POSTHOG_HOST`). PostHog is fully optional — no key means no analytics and env-fallback flags only.

## Gotchas

- Workspace rule: after editing any `frontend/` file, run `npm run format:check` (a hook also enforces this).
- Strict TS: `noUnusedLocals`/`noUnusedParameters` — prefix intentionally unused with `_`.
- New API calls go in `src/lib/api.ts` or a sibling module using `authedGet`; get the token from `useAuth()`.
