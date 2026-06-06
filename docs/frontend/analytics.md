# Frontend analytics (PostHog)

The SPA uses [PostHog](https://posthog.com/) for product analytics. This is the
canonical taxonomy for the events and properties the frontend emits. PostHog is
initialized in [`frontend/src/providers/posthog-provider.tsx`](../../frontend/src/providers/posthog-provider.tsx)
and stays **fully disabled** unless `VITE_POSTHOG_KEY` is set, so none of the
below fires in environments without a key.

## Auto-captured events

Configured explicitly in `posthog.init`:

| Event | When | Notes |
|---|---|---|
| `$pageview` | App mount / load | `capture_pageview: true`. Switch to `"history_change"` once a client router is added. |
| `$pageleave` | Tab/page unload | `capture_pageleave: true`. Powers session/bounce metrics. |
| `$autocapture` | Every element click (buttons, links, etc.) | `autocapture: true`. Buttons carry the structured attributes below. |

We intentionally rely on autocapture for click tracking rather than wiring a
`capture()` call onto every button.

## Global super properties

Registered once in `loaded` and attached to **every** event (including each
`$autocapture` click and `$pageview`):

| Property | Source | Default |
|---|---|---|
| `app_environment` | `VITE_APP_ENV` | Vite `MODE` |
| `app_version` | `VITE_APP_VERSION` | `package.json` version (`"0.0.0"`) |
| `git_sha` | `VITE_GIT_SHA` | `"dev"` |

These are injected at build time via [`frontend/vite.config.ts`](../../frontend/vite.config.ts).
The deploy script ([`scripts/deploy-frontend.sh`](../../scripts/deploy-frontend.sh))
sets `VITE_APP_ENV` to the target environment (`beta`/`prod`) and `VITE_GIT_SHA`
to the commit SHA, so builds are distinguishable in PostHog. See
[`.env.example`](../../.env.example) for the optional vars.

## Button click convention

The shared [`Button`](../../frontend/src/components/ui/button.tsx) component emits
PostHog `data-ph-capture-attribute-*` attributes. PostHog automatically lifts
these onto the `$autocapture` event, so each click carries structured props
instead of relying on the rendered label text:

| Attribute | Source | Example |
|---|---|---|
| `data-ph-capture-attribute-component` | constant | `button` |
| `data-ph-capture-attribute-variant` | `variant` prop | `default`, `outline`, … |
| `data-ph-capture-attribute-size` | `size` prop | `default`, `sm`, … |
| `data-ph-capture-attribute-name` | optional `analyticsName` prop | `get_started` |

Pass `analyticsName` to give a click a stable identifier independent of its
label:

```tsx
<Button analyticsName="get_started">Get Started</Button>
```

In PostHog these surface on the `$autocapture` event as properties named
`component`, `variant`, `size`, and `name` — filter or break down events by
them (e.g. all clicks where `name = get_started`).

## Domain events

Named events captured explicitly for product-specific moments. Use these
sparingly, when autocapture cannot express the intent.

| Event | Where | Notes |
|---|---|---|
| `homepage_viewed` | [`frontend/src/App.tsx`](../../frontend/src/App.tsx) | Template for future named events. Distinct from the auto `$pageview`. |
| `sign_up_submitted` | [`auth-provider.tsx`](../../frontend/src/providers/auth-provider.tsx) | Fired when a sign-up request starts. |
| `sign_up_succeeded` | `auth-provider.tsx` | Account created and session established. |
| `sign_up_failed` | `auth-provider.tsx` | Carries `reason` (backend error code or `unknown`). |
| `sign_in_submitted` | `auth-provider.tsx` | Fired when a sign-in request starts. |
| `sign_in_succeeded` | `auth-provider.tsx` | Session established. |
| `sign_in_failed` | `auth-provider.tsx` | Carries `reason` (backend error code or `unknown`). |

To add one: `posthog?.capture("event_name", { /* props */ })`.

## Identification

On successful sign in / sign up, the user is identified with
`posthog.identify(user.id, { email, name })`; on sign out, `posthog.reset()`
clears the identity. Because `person_profiles: "identified_only"` is set,
anonymous activity stays anonymous until the user authenticates.

## Feature flags

| Flag | Controls |
|---|---|
| `signup-signin` | Whether the sign up / sign in surface (landing links + `/signin`, `/signup` routes) is shown. Read via [`use-auth-flag.ts`](../../frontend/src/hooks/use-auth-flag.ts). When PostHog is disabled (no key), it falls back to `VITE_AUTH_ENABLED === "true"` (default off). |

## Limitations & future work

- **`dist-landing` artifact:** the ~15-element landing page in
  `frontend/dist-landing/` is a prebuilt artifact with no React source in
  `src/`. Autocapture still records its clicks at runtime (when a key is set),
  but it cannot receive the `data-ph-capture-attribute-*` enrichment until its
  source is added.
- **Routing:** the app now uses `react-router-dom`, but `capture_pageview`
  remains `true` (load-time pageview). Switch it to `"history_change"` to emit a
  `$pageview` on every client-side route change.
