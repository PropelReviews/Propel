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
| `$pageview` | Client-side route changes | `capture_pageview: "history_change"` emits a pageview on every SPA navigation. |
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
| `landing_viewed` | [`LandingPage.tsx`](../../frontend/src/pages/landing/LandingPage.tsx) | Fired on landing page mount. |
| `waitlist_joined` | Backend: [`app/services/waitlist.py`](../../backend/app/services/waitlist.py) | **Server-side** event captured after a waitlist email is persisted. Carries `email`. Drives the PostHog workflow that emails new signups to the team. Deliberately not fired from the frontend so ad-blockers can't skip it and the workflow can't double-fire. |

To add one: `posthog?.capture("event_name", { /* props */ })`.

## Identification

On successful sign in / sign up, the user is identified with
`posthog.identify(user.id, { email, name })`; on sign out, `posthog.reset()`
clears the identity. Because `person_profiles: "identified_only"` is set,
anonymous activity stays anonymous until the user authenticates.

On refresh, a cached user profile re-identifies PostHog immediately (before
`GET /users/me` completes) so feature flags that target identified users stay
stable. Feature flags and distinct IDs are also bootstrapped from
`localStorage` on init so the first paint matches the previous session.

## Feature flags

| Flag | Controls |
|---|---|
| `signup-signin` | Whether the sign up / sign in surface (`/signin`, `/signup` routes and homepage auth CTAs) is shown. On the landing site it gates the cloud CTAs: when **on**, "Open app" / "Try Propel Cloud" links render; when **off**, they are replaced by the email waitlist form ([`waitlist-form.tsx`](../../frontend/src/components/landing/waitlist-form.tsx)). Read via [`use-auth-flag.ts`](../../frontend/src/hooks/use-auth-flag.ts). When PostHog is disabled (no key), it falls back to `VITE_AUTH_ENABLED === "true"` (default off). |

## Error tracking

Configured in `posthog.init`:

| Setting | Value | Notes |
|---|---|---|
| `capture_exceptions` | `true` | Autocaptures unhandled JS errors and promise rejections. |
| `PostHogErrorBoundary` | wraps app | Captures React render errors; shows a fallback UI. |

Unexpected auth failures (non-API errors during bootstrap, sign-in, or sign-up) are
also sent via `posthog.captureException()`. Expected validation/auth errors
(wrong password, duplicate email) stay as domain events only (`sign_in_failed`, etc.).

### Source maps

Production deploys upload source maps via `@posthog/rollup-plugin` when
`POSTHOG_PERSONAL_API_KEY` and `POSTHOG_PROJECT_ID` are set in the build
environment (CI GitHub Actions variables). Maps are keyed by release
`propel-frontend` + `VITE_GIT_SHA`. They are deleted from the S3 artifact after
upload (`deleteAfterUpload: true`).

## Session replay

Configured in `posthog.init`:

```ts
session_recording: { maskAllInputs: true }
```

All form inputs (including sign-in / sign-up) are masked in recordings. Session
replay must also be enabled in your PostHog project settings.

## Limitations & future work

- None currently. (The landing page is real React source under
  `frontend/src/pages/landing/` — built to `dist-landing/` — so its buttons
  carry the full `data-ph-capture-attribute-*` enrichment.)
