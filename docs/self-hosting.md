# Self-hosting Propel

Propel is fully open source and designed to run in your own infrastructure. Your
data stays in your Postgres database; nothing phones home unless you opt in to
analytics (PostHog).

This guide covers:

- Running the stack with Docker Compose (local dev or a single-server deployment)
- Every environment variable you need to configure
- Step-by-step setup for the two supported data integrations: **GitHub** and
  **Linear**

For AWS production deployment with Terraform, see the
[deployment bootstrap runbook](deployment/bootstrap.md).

---

## What you are deploying

```
Browser (React SPA)
        │
        ▼
   FastAPI backend  ◄──── OAuth callbacks (GitHub login, Linear connect)
        │
        ├── Postgres (app data + Dagster state)
        │
        └── Dagster ingestion (hourly schedule)
                 │
                 ▼
            Meltano taps ──► GitHub App / Linear OAuth tokens
```

| Service | Default port | Role |
|---------|--------------|------|
| `postgres` | 5432 | Application database |
| `backend` | 8000 | FastAPI API, auth, webhooks, connection management |
| `frontend` | 5173 | React dashboard (Vite dev server in Compose; static build in production) |
| `ingestion` | 3001 | Dagster webserver + daemon (hourly data extraction) |
| `dask-worker` | — | Executes ingestion jobs submitted by Dagster |
| `frontend-landing` | 5174 | Marketing landing page (optional; not required for the app) |

Dagster UI: <http://localhost:3001> (local). The hourly schedule discovers
connected accounts and pulls data from GitHub and Linear.

---

## Quick start (Docker Compose)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- [Git](https://git-scm.com/)

### 1. Clone and configure

```bash
git clone https://github.com/PropelReviews/Propel
cd Propel
cp .env.example .env
```

Edit `.env` — at minimum set a strong `JWT_SECRET` before exposing the stack
beyond localhost:

```bash
openssl rand -hex 32   # paste into JWT_SECRET=
```

### 2. Start the stack

```bash
docker compose up -d
```

On first start the backend runs Alembic migrations automatically. The ingestion
container installs Meltano plugins on first boot (can take several minutes).

| URL | Service |
|-----|---------|
| <http://localhost:5173> | Dashboard |
| <http://localhost:8000/health> | API health check |
| <http://localhost:3001> | Dagster UI |

### 3. Create your first user

With `AUTH_REGISTRATION_ENABLED=true` (the `.env.example` default), register at
the sign-up screen or via the API:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-secure-password"}'
```

When PostHog is not configured, also set `VITE_AUTH_ENABLED=true` in `.env` and
restart the frontend so the auth UI is visible.

### 4. Configure integrations

GitHub and Linear require provider-side apps **and** the matching env vars below.
Without them you can use Propel for auth and org management, but no toolchain
data will be ingested.

Continue to [Integration setup](#integration-setup) once your `.env` is ready.

---

## Production on a single server

Docker Compose is the supported path for a simple self-hosted deployment. For a
public-facing install you will need:

1. **HTTPS** — OAuth providers require stable `https://` callback URLs.
2. **A reverse proxy** (nginx, Caddy, Traefik) terminating TLS and routing:
   - `app.yourdomain.com` → frontend (`5173` dev server, or serve a static
     `npm run build` from nginx)
   - `api.yourdomain.com` → backend (`8000`)
3. **Matching env vars** — set `OAUTH_CALLBACK_BASE_URL`,
   `FRONTEND_BASE_URL`, `CORS_ALLOWED_ORIGINS`, and `VITE_API_URL` to your
   public URLs.
4. **`APP_ENV=production`** — the API rejects weak `JWT_SECRET` values in
   production.

### Building the frontend for production

The Compose `frontend` service runs the Vite dev server. For production, build
static assets and serve them from your reverse proxy:

```bash
cd frontend
VITE_API_URL=https://api.yourdomain.com npm run build
# Serve dist/ from nginx/Caddy at app.yourdomain.com
```

Set `VITE_AUTH_ENABLED=true` at build time if you are not using PostHog feature
flags.

### Building the backend for production

```bash
docker build -f infrastructure/docker/backend.prod.Dockerfile -t propel-api backend
docker run -d --name propel-api -p 8000:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql://propel:YOUR_PASSWORD@YOUR_DB_HOST:5432/propel \
  -e APP_ENV=production \
  propel-api
```

Run a separate ingestion container with the same image and env, using command
`dagster-service` (see [`backend/entrypoint.sh`](../backend/entrypoint.sh)).

For a managed AWS deployment (ECS, Aurora, CloudFront), follow the
[bootstrap runbook](deployment/bootstrap.md).

---

## Environment variables

Copy [`.env.example`](../.env.example) to `.env`. Variables are read by the
backend and ingestion containers; frontend build-time vars are noted separately.

### Core (required)

| Variable | Secret? | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | No | Postgres username (default `propel`) |
| `POSTGRES_PASSWORD` | **Yes** | Postgres password |
| `POSTGRES_DB` | No | Database name (default `propel`) |
| `DATABASE_URL` | **Yes** | SQLAlchemy URL. Compose overrides this for container networking; use `postgresql://user:pass@postgres:5432/propel` inside Compose, `localhost` when running the API on the host |
| `JWT_SECRET` | **Yes** | Signs session JWTs and GitHub install-state HMACs. Generate with `openssl rand -hex 32`. Must be ≥ 32 characters when `APP_ENV` is `production` or `beta` |
| `APP_ENV` | No | `development` (default), `beta`, or `production`. Controls startup validation |

### Auth and signup

| Variable | Secret? | Default | Description |
|----------|---------|---------|-------------|
| `AUTH_REGISTRATION_ENABLED` | No | `false` | Allow `POST /api/v1/auth/register`. Set `true` for open signup |
| `JWT_LIFETIME_SECONDS` | No | `3600` | Session token lifetime |
| `AUTH_RATE_LIMIT_MAX_REQUESTS` | No | `10` | Per-IP login/register rate limit |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate-limit window |

### URLs and CORS

These must match your public hostnames in production.

| Variable | Secret? | Example (local) | Description |
|----------|---------|-----------------|-------------|
| `OAUTH_CALLBACK_BASE_URL` | No | `http://localhost:8000` | **API** origin — where OAuth providers send the authorization code |
| `FRONTEND_BASE_URL` | No | `http://localhost:5173` | **SPA** origin — where the API redirects the browser after OAuth |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:5173,...` | Comma-separated browser origins allowed to call the API |
| `VITE_API_URL` | No | `http://localhost:8000` | **Frontend build-time** — API base URL baked into the SPA (`npm run build`) |

### Google login (optional)

| Variable | Secret? | Description |
|----------|---------|-------------|
| `OAUTH_GOOGLE_CLIENT_ID` | No | Google OAuth client ID |
| `OAUTH_GOOGLE_CLIENT_SECRET` | **Yes** | Google OAuth client secret |

Register redirect: `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/google/callback`

### GitHub — ingestion GitHub App

These power **data extraction** and org connection. Create a
[GitHub App](https://github.com/settings/apps/new) (see
[GitHub integration](#github-integration) below).

| Variable | Secret? | Description |
|----------|---------|-------------|
| `GITHUB_APP_ID` | **Yes** | Numeric App ID |
| `GITHUB_APP_PRIVATE_KEY` | **Yes** | PEM private key. Paste with literal `\n` escapes on one line, or as a multi-line value |
| `GITHUB_APP_WEBHOOK_SECRET` | **Yes** | Webhook signing secret from the App settings |
| `GITHUB_APP_SLUG` | No | App URL slug (e.g. `my-propel` for `github.com/apps/my-propel`) |

Webhook URL to register on the App:

```
{OAUTH_CALLBACK_BASE_URL}/api/v1/webhooks/github
```

### GitHub — user login (optional but recommended)

Reuse the same GitHub App for sign-in, or use a standalone OAuth app.

**Option A — reuse the ingestion App (recommended):**

| Variable | Secret? | Description |
|----------|---------|-------------|
| `GITHUB_APP_CLIENT_ID` | No | App **Client ID** (`Iv1…`) from the App's "Identifying and authorizing users" section |
| `GITHUB_APP_CLIENT_SECRET` | **Yes** | Generated client secret (distinct from the App ID and private key) |

**Option B — standalone OAuth app (fallback):**

| Variable | Secret? | Description |
|----------|---------|-------------|
| `OAUTH_GITHUB_CLIENT_ID` | No | OAuth App client ID |
| `OAUTH_GITHUB_CLIENT_SECRET` | **Yes** | OAuth App client secret |

Register these redirect URLs on the **API** origin:

| Flow | Redirect URL |
|------|--------------|
| Sign in / sign up | `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/login/callback` |
| Connect with GitHub (profile) | `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/link/callback` |
| fastapi-users built-in | `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/callback` |

When using the GitHub App for login, also add the sign-in and link callback URLs
to the App's **User authorization callback URL** list.

### Linear — data connection

Linear is a **data source**, not a login provider. Create an OAuth application at
[Linear → Settings → API → OAuth applications](https://linear.app/settings/api/applications/new).

| Variable | Secret? | Description |
|----------|---------|-------------|
| `OAUTH_LINEAR_CLIENT_ID` | No | OAuth application Client ID |
| `OAUTH_LINEAR_CLIENT_SECRET` | **Yes** | OAuth application Client Secret |
| `TOKEN_ENCRYPTION_KEY` | **Yes** | Fernet key for encrypting stored OAuth tokens at rest. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

Register callback URL:

```
{OAUTH_CALLBACK_BASE_URL}/api/v1/connections/linear/callback
```

### Ingestion tuning

| Variable | Secret? | Default | Description |
|----------|---------|---------|-------------|
| `INGESTION_BACKFILL_DAYS` | No | `90` | How far back the first sync pulls repo activity. Copilot metrics are capped by GitHub at ~28 days regardless |

### Analytics (optional — PostHog)

Propel works without PostHog. When unset, tracing and product analytics are
disabled.

| Variable | Secret? | Consumed by | Description |
|----------|---------|-------------|-------------|
| `POSTHOG_TOKEN` | No* | API + frontend | Project API key (write-only; safe in frontend builds) |
| `POSTHOG_HOST` | No | API + frontend | PostHog ingest host via managed reverse proxy (default `https://metrics.propelreview.com`) |
| `POSTHOG_PERSONAL_API_KEY` | **Yes** | API (server) + frontend build | Personal API key for fast feature-flag evaluation and source-map upload |
| `POSTHOG_PROJECT_ID` | No | Frontend build | Project ID for source-map upload |
| `OTEL_SERVICE_NAME` | No | API | OpenTelemetry service name (default `propel-backend`) |
| `OTEL_SERVICE_NAME_INGESTION` | No | Ingestion | OTEL name for Dagster logs (default `propel-ingestion`) |
| `VITE_AUTH_ENABLED` | No | Frontend build | Show auth UI when PostHog is disabled (default off) |
| `VITE_CHART_DEMO_ENABLED` | No | Frontend build | Show chart demo when PostHog is disabled (default off) |

\*Treat as non-secret for the write-only project key; keep personal API keys secret.

### Ports (optional overrides)

| Variable | Default | Service |
|----------|---------|---------|
| `POSTGRES_PORT` | `5432` | Postgres |
| `BACKEND_PORT` | `8000` | API |
| `FRONTEND_PORT` | `5173` | Dashboard |
| `DAGSTER_PORT` | `3001` | Dagster UI |
| `DASK_DASHBOARD_PORT` | `8787` | Dask dashboard (embedded in ingestion container) |

### Legacy / manual testing only

| Variable | Description |
|----------|-------------|
| `LINEAR_API_KEY` | Developer token for manual `tap-linear` testing — **not** used by the production OAuth flow |

---

## Integration setup

Propel currently supports two data integrations:

| Integration | Auth model | What gets ingested |
|-------------|------------|-------------------|
| **GitHub** | GitHub App installation per org | Commits, pull requests, issues, org members, user profiles, Copilot usage (when available) |
| **Linear** | OAuth (`actor=app`) per workspace | Issues |

Signing in with GitHub does **not** connect your org for ingestion — those are
separate steps.

---

## GitHub integration

GitHub requires a **GitHub App** for data ingestion. User login can reuse the
same App or a standalone OAuth app.

### 1. Create a GitHub App

Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
(or your org's settings if the App should be org-owned).

| Setting | Value |
|---------|-------|
| **Homepage URL** | Your Propel URL (e.g. `https://app.yourdomain.com`) |
| **Webhook URL** | `{OAUTH_CALLBACK_BASE_URL}/api/v1/webhooks/github` |
| **Webhook secret** | Generate one; copy to `GITHUB_APP_WEBHOOK_SECRET` |
| **Where can this app be installed?** | Any account (typical for self-host) |

### 2. Repository permissions

| Permission | Access | Why |
|------------|--------|-----|
| **Contents** | Read-only | Commit history and GitHub Releases (deployment frequency) |
| **Issues** | Read-only | Issues and comments |
| **Metadata** | Read-only | Required for repository access |
| **Pull requests** | Read-only | PRs, reviews, review comments |
| **Actions** | Read-only | Workflow runs (CI/CD activity primitives) |

### 3. Organization permissions

| Permission | Access | Why |
|------------|--------|-----|
| **Members** | Read-only | Org roster sync and admin-role mapping |
| **Copilot metrics** | Read-only | Copilot usage metrics (optional — skipped automatically when unavailable) |

### 4. Subscribe to events

Under **Subscribe to events**, enable:

- **Installation** — required (tracks install, suspend, revoke, permission changes)

### 5. Generate credentials

1. Note the **App ID** → `GITHUB_APP_ID`
2. Generate a **private key** → `GITHUB_APP_PRIVATE_KEY`
3. Note the **App slug** from the URL → `GITHUB_APP_SLUG`

### 6. Enable user login (optional)

On the same App, under **Identifying and authorizing users**:

1. Add **Callback URL(s)**:
   - `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/login/callback`
   - `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/link/callback`
2. Under **Account permissions**, set **Email addresses** to **Read-only**
3. Generate a **Client secret** → `GITHUB_APP_CLIENT_SECRET`
4. Copy the **Client ID** (`Iv1…`) → `GITHUB_APP_CLIENT_ID`

### 7. Set env vars and restart

Add the GitHub App variables to `.env`, then:

```bash
docker compose up -d backend ingestion dask-worker
```

### 8. Connect a GitHub org in Propel

1. Sign in to Propel and create (or join) a workspace.
2. As a workspace **admin**, go to **Settings → Workspace → Connections**.
3. Click **Connect GitHub** — you are redirected to install the App on your org.
4. After installation, GitHub redirects back and Propel binds the installation
   to your workspace.

Alternatively, the hourly Dagster discovery job and the GitHub `installation`
webhook auto-provision connections when an App is installed.

### 9. Verify ingestion

```bash
# Trigger a run immediately (don't wait for the hourly schedule):
docker compose exec ingestion python -m app.ingestion.cli run

# Or open the Dagster UI and launch org_ingestion_job:
open http://localhost:3001
```

Check Dagster run logs or query Postgres for rows in `raw_record`.

---

## Linear integration

Linear connects via OAuth at the workspace level (`actor=app`), so the token
represents the Propel application inside the workspace — the right model for
team analytics.

### 1. Create a Linear OAuth application

Go to [Linear → Settings → API → OAuth applications → New](https://linear.app/settings/api/applications/new).

| Setting | Value |
|---------|-------|
| **Redirect URI** | `{OAUTH_CALLBACK_BASE_URL}/api/v1/connections/linear/callback` |
| **Scopes** | `read` |
| **Public / Authorize for any workspace** | Enable if multiple workspaces will connect |

### 2. Set env vars

```bash
OAUTH_LINEAR_CLIENT_ID=...
OAUTH_LINEAR_CLIENT_SECRET=...
TOKEN_ENCRYPTION_KEY=...   # Fernet key — required for any OAuth token storage
```

Restart the backend:

```bash
docker compose up -d backend ingestion
```

### 3. Connect a Linear workspace in Propel

1. Sign in as a workspace member with the `connections:manage` permission
   (admins have this by default).
2. Go to **Settings → Workspace**. Each tool (GitHub, Linear) has its own
   integration card.
3. Click **Connect Linear** — Propel opens Linear’s authorize page in a new tab.
4. Approve the app. On success that tab returns to workspace settings with
   Linear showing as connected. You can also stay on the original tab and click
   **I've connected it** to refresh status.

#### Already installed (no OAuth callback)

If Linear shows the app as already installed, it will not redirect with an
authorization code. Revoke and reconnect:

1. In Linear: **Settings → Installed Applications** → find Propel → **Manage** →
   **Revoke Access**
2. Return to Propel and click **Connect Linear** again
3. Click **I've connected it** if the original tab is still open

### 4. Verify ingestion

Linear issues, comments, projects, and issue description edits are pulled by
Meltano jobs (`linear_issues_sync`, `linear_comments_sync`,
`linear_projects_sync`, `linear_description_edits_sync`), scheduled hourly via
Dagster alongside GitHub jobs:

```bash
docker compose exec ingestion python -m app.ingestion.cli run --job linear_issues_sync
docker compose exec ingestion python -m app.ingestion.cli run --job linear_comments_sync
```

---

## End-to-end checklist

Use this when bringing up a new self-hosted instance:

- [ ] Clone repo, copy `.env.example` → `.env`
- [ ] Set `JWT_SECRET` (≥ 32 chars for production)
- [ ] Set `APP_ENV` appropriately
- [ ] Set `AUTH_REGISTRATION_ENABLED=true` (or configure PostHog `signup-signin` flag)
- [ ] Set `VITE_AUTH_ENABLED=true` at frontend build time if not using PostHog
- [ ] Configure public URLs: `OAUTH_CALLBACK_BASE_URL`, `FRONTEND_BASE_URL`,
      `CORS_ALLOWED_ORIGINS`, `VITE_API_URL`
- [ ] Create and configure the **GitHub App**; set all `GITHUB_APP_*` vars
- [ ] (Optional) Set `GITHUB_APP_CLIENT_ID` / `GITHUB_APP_CLIENT_SECRET` for login
- [ ] Create **Linear OAuth app**; set `OAUTH_LINEAR_*` and `TOKEN_ENCRYPTION_KEY`
- [ ] `docker compose up -d`
- [ ] Register / sign in, create a workspace
- [ ] Connect GitHub org and Linear workspace in workspace settings
- [ ] Confirm ingestion runs in Dagster UI or via CLI

---

## Troubleshooting

### Auth UI is hidden

PostHog gates the sign-in UI behind the `signup-signin` feature flag. Without
PostHog, set `VITE_AUTH_ENABLED=true` and rebuild/restart the frontend.

### GitHub install link returns 503

`GITHUB_APP_SLUG` is missing or incorrect. The slug is the path segment in
`https://github.com/apps/<slug>`.

### GitHub webhook signature failures

Ensure `GITHUB_APP_WEBHOOK_SECRET` matches the secret configured on the GitHub
App, and that your reverse proxy forwards the raw request body to the API.

### Linear connect returns 503

`OAUTH_LINEAR_CLIENT_ID` and `OAUTH_LINEAR_CLIENT_SECRET` must both be set.
`TOKEN_ENCRYPTION_KEY` is required to store tokens.

### Ingestion runs but pulls no data

- Confirm a `connected_accounts` row exists with `status='active'` for the
  provider (check via the connections API or workspace settings).
- For GitHub, verify the App is installed on the org and repository permissions
  were granted.
- For Linear, re-authorize if the token expired and refresh failed.

### Workspace shows “Needs reconnect” on an integration

Ingestion marked the connection `paused` / `revoked` after an auth or install
failure (Linear token refresh failure, missing GitHub App installation, etc.).
Use **Reconnect** / **Reinstall** on the Workspace Integrations card. Successful
OAuth / installation sync clears the error and sets status back to `active`.

### Meltano install is slow or fails on first boot

The ingestion container runs `meltano install` on first start. Watch progress:

```bash
docker logs -f propel-ingestion
```

Restart the ingestion and dask-worker services after a successful install.

### Weak JWT secret in production

```
JWT_SECRET must be a random string of at least 32 characters in production environments.
```

Generate a new secret with `openssl rand -hex 32` and update `.env`.

---

## Related docs

- [Backend README](../backend/README.md) — API endpoints, auth, ingestion details
- [Backend data model](backend/data-model.md) — tenants, connections, identity linking
- [Meltano extraction](../backend/meltano/README.md) — taps, jobs, per-run env
- [Orchestration](../orchestration/README.md) — Dagster schedules and job chain
- [Infrastructure](../infrastructure/README.md) — containers and local stack
- [AWS bootstrap runbook](deployment/bootstrap.md) — Terraform production deploy
