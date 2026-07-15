# PostHog Self-driving Setup Report

_Generated: 2026-07-15_

## Summary

PostHog Self-driving has been configured for the **Propel Reviews** project. Session Replay, Error Tracking, GitHub Issues, and Support are wired as signal sources; a scout troop of 4 scouts (including one custom auth-health scout) is scheduled to run every 24 hours. Findings will start appearing in your [Self-driving inbox](https://us.posthog.com/project/245238/inbox) within approximately 30 minutes.

---

## AI data processing

**Status:** Approved at the organization level (enforced by the setup wizard before this run began).

---

## GitHub

**Status:** Already connected — integration `PropelReviews` (id: 175452), connected 2026-06-06 by Sam Rossilli.

---

## Products enabled

| Product | Status | Notes |
|---|---|---|
| Session Replay | Already enabled | `session_recording_opt_in: true` confirmed in project settings. `posthog.init` is clean — no `disable_session_recording` override. |
| Error Tracking | Already enabled | `autocapture_exceptions_opt_in: true` confirmed. `posthog.init` has `capture_exceptions: true` — no override. |
| Support (Conversations) | Not yet enabled | `products-enable` tool was unavailable in this PostHog version. **Tickets will not arrive until Conversations is enabled and a channel connected.** See follow-ups. |

---

## Signal sources

| Source product | Source type | Action | Notes |
|---|---|---|---|
| `signals_scout` | `cross_source_issue` | **Default ON** | Scout gate is on by default — no config row needed. |
| `error_tracking` | `issue_created` | **Enabled** | id: `019f65f7-4e40-7170-b5e0-7ee689333de3` |
| `error_tracking` | `issue_reopened` | **Enabled** | id: `019f65f7-51ea-70f5-85af-e2f1c70ba8ea` |
| `error_tracking` | `issue_spiking` | **Enabled** | id: `019f65f7-55c5-7644-91ff-3eefdc91d2ec` |
| `session_replay` | `session_analysis_cluster` | **Enabled** | id: `019f65f7-6ccc-7f59-930f-b8b51cecd302`, sample_rate: 0.1 |
| `conversations` | `ticket` | **Enabled (dormant)** | id: `019f65f7-59d9-79df-a010-0a68e5714cb6`. Stays dormant until an inbound channel is connected and Conversations is enabled. |
| `github` | `issue` | **Enabled** | id: `019f65f9-0732-7f52-be43-8034d1d4eecb` |
| `llm_analytics` | — | **Skipped** | Not a v1 signal source responder. |
| `logs` | — | **Skipped** | Not a v1 signal source responder. |

---

## Connected tools

| Tool | Status | Details |
|---|---|---|
| GitHub Issues | **Connected by this setup** | Warehouse source id: `019f65f8-ec77-0000-28ea-201e67b95674`. Repository: `PropelReviews/Propel`. Syncing `issues` table (incremental on `updated_at`). First sync started automatically. Additional tables can be enabled in the PostHog UI under Data → Sources. |
| Linear | Not used | Not selected. |
| Zendesk | Not used | Not selected. |
| pganalyze | Not used | Not selected. |

---

## Scout troop

**Enabled (4 scouts):**

| Scout | Reason |
|---|---|
| `signals-scout-general` | Always on — sweeps cross-product correlations and surfaces no specialist covers. Was already enabled. |
| `signals-scout-product-analytics` | Most-used specialist — product analytics onboarding completed, posthog-js installed with events tracked, saved insights and dashboards in use. |
| `signals-scout-feature-flags` | Second specialist — feature flags in active use throughout the codebase; `create_feature_flag` and `create_early_access_feature` onboarding completed; flags used extensively in M3–M5 metric authoring development. |
| `signals-scout-auth-health` | Custom scout (see below). |

**Disabled (23 scouts):**

| Scout | Reason |
|---|---|
| `signals-scout-error-tracking` | Covered by the native `error_tracking` signal source (step 4). Not a re-enable candidate. |
| `signals-scout-session-replay` | Covered by the native `session_replay` signal source (step 4). Not a re-enable candidate. |
| `signals-scout-ai-observability` | No confirmed `$ai_*` events or LLM SDK usage in this repo. Enable if AI observability is added. |
| `signals-scout-anomaly-detection` | Not in the top-1–2 product surfaces for this project. |
| `signals-scout-apm` | No APM/OpenTelemetry spans confirmed. Enable if distributed tracing is added. |
| `signals-scout-csp-violations` | No CSP reporting configured. Enable if a Content-Security-Policy with PostHog reporting is added. |
| `signals-scout-customer-analytics` | No group analytics configured (`has_group_types: false`). Enable if B2B account analytics are added. |
| `signals-scout-data-pipelines` | No CDP destinations, hog flows, or batch exports confirmed. Enable if pipelines are added. |
| `signals-scout-data-warehouse` | Kept small — GitHub Issues is the only warehouse source and the connection is brand-new with no baseline. Enable later if warehouse health monitoring is needed. |
| `signals-scout-experiments` | Experiments in product_intents but not a top-ranked surface vs product-analytics and feature-flags. Enable if A/B experiments are launched. |
| `signals-scout-health-checks` | Troop size constraint. Enable if PostHog setup health issues need active monitoring. |
| `signals-scout-inbox-validation` | Not appropriate for a fresh setup with no resolved reports. Enable after the first wave of reports are resolved. |
| `signals-scout-ingestion-warnings` | Troop size constraint. Enable if ingestion drops or warnings appear. |
| `signals-scout-insight-alerts` | Troop size constraint. Enable if alert monitoring is needed. |
| `signals-scout-logs` | Logs product in `product_intents` but not a top-2 surface. Enable if log monitoring becomes important. |
| `signals-scout-mcp-tool-calls` | Troop size constraint. Enable if MCP tool telemetry is captured. |
| `signals-scout-observability-gaps` | Troop size constraint. Enable to surface events with no insight coverage. |
| `signals-scout-replay-vision` | No Replay Vision scanners configured. Enable if scanners are set up. |
| `signals-scout-revenue-analytics` | No payment SDK or revenue data connected. Enable if Stripe or another revenue source is added. |
| `signals-scout-skills-store` | Troop size constraint. Enable if skill hygiene monitoring is needed. |
| `signals-scout-surveys` | 0 surveys in use. Enable if PostHog surveys are launched. |
| `signals-scout-web-analytics` | `signals-scout-product-analytics` is the higher-ranked specialist for this project's traffic. Enable if referrer/UTM attribution monitoring is needed. |
| `signals-scout-web-vitals` | Troop size constraint. Enable if Core Web Vitals monitoring is needed (Web Vitals autocapture is already on). |

---

## Custom scouts

### `signals-scout-auth-health` — created

**What it watches:** Sign-up and sign-in authentication flows using the confirmed event set: `sign_up_submitted` → `sign_up_succeeded` / `sign_up_failed` (with `reason` property) and `sign_in_submitted` → `sign_in_succeeded` / `sign_in_failed` (with `reason` property).

**Discriminator:** Fires only when (1) the `failed/submitted` ratio spikes above the 7-day rolling mean, OR (2) a new `reason` code appears that wasn't present in the prior 7-day window and affects more than one user. Neither condition fires on fewer than 5 total failures to avoid low-volume noise.

**Why no built-in covers it:** `signals-scout-error-tracking` watches `$exception` events only, not custom auth events. `signals-scout-product-analytics` watches saved PostHog funnels — there are none yet for this flow. `signals-scout-general` may catch broad anomalies but won't perform the fine-grained `reason`-code clustering this scout does.

**Noise escape hatch:** If this scout turns out noisy, set `emit: false` on its config in PostHog → Self-driving to switch it to dry-run mode.

**Surfaces considered and ruled out:**

| Surface | Filter that eliminated it |
|---|---|
| GitHub workspace onboarding (connect-tools.tsx) | No PostHog `capture()` calls in that component — autocapture button clicks are too fuzzy to build a reliable scout |
| Metric activation funnel (builder / activate-sheet) | No confirmed custom event names in the metrics builder or activation components |
| Waitlist conversion | No confirmed capture calls in the landing page components |

---

## Follow-ups

- [ ] **Enable Conversations (Support product):** The `products-enable` tool was unavailable in this PostHog version. Enable Session Replay, Error Tracking, and Conversations manually at [Project Settings → Products](https://us.posthog.com/project/245238/settings). Session Replay and Error Tracking appear already on from project settings, but Conversations (`conversations_enabled: null`) needs to be turned on.
- [ ] **Connect a Support inbound channel:** Once Conversations is enabled, connect an email inbox, Slack channel, or other inbound channel so that support tickets flow into the inbox. The `conversations/ticket` signal source responder is already enabled and will start emitting automatically once a channel exists.
- [ ] **Instrument the GitHub workspace onboarding flow:** Add PostHog `capture()` calls to `connect-tools.tsx` — e.g. `github_app_install_opened`, `github_connection_checked`, `github_connection_succeeded`, `github_connection_not_found` — so this critical activation step becomes watchable by a scout or saved funnel.
- [ ] **Instrument the metric creation/activation flow:** Add capture calls to the metric builder and `activate-sheet.tsx` (e.g. `metric_builder_opened`, `metric_activated`, `metric_definition_saved`) to enable funnel and scout coverage of the core product loop.
- [ ] **Create saved funnels in PostHog:** `signals-scout-product-analytics` watches the team's saved PostHog funnels. Create at least one funnel insight (e.g. sign-up → first metric view → metric activated) so the product-analytics scout has flows to monitor.
- [ ] **GitHub Issues — additional tables:** The warehouse source syncs only the `issues` table. Enable `pull_requests`, `comments`, or other tables in PostHog → Data → Sources → PropelReviews/Propel if needed.
- [ ] **Re-enable specialist scouts as surfaces grow:** See the disabled-scout table above for per-scout re-enable triggers (e.g. enable `signals-scout-ai-observability` if `$ai_*` events are added, `signals-scout-experiments` when A/B tests launch).

---

## What happens next

The scout coordinator picks up freshly enabled configs within **~30 minutes**. After that, scouts run on their 24-hour schedule and file validated findings as reports in your [Self-driving inbox](https://us.posthog.com/project/245238/inbox). Error tracking and GitHub Issues findings can arrive sooner — those are event-driven, not scout-driven. Immediately actionable reports can spawn coding tasks directly from the inbox.
