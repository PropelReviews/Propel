# Backend

FastAPI application and data extraction for Propel.

## Stack

- **API:** FastAPI (Python 3.12)
- **ORM:** SQLAlchemy 2.0 (async) + Alembic + asyncpg
- **Auth:** fastapi-users (MIT) + httpx-oauth — email/password, JWT, Google/GitHub login OAuth
- **Extraction:** Meltano (co-located in `meltano/` for shared Python environment)

## Purpose

The backend serves the Propel API and orchestrates data extraction from your toolchain (GitHub, Linear, Cursor) into Postgres via Meltano.

```
Your tools (GitHub, Linear, Cursor)
        │
        ▼
   meltano/          ← extraction
        │
        ▼
   Postgres         ← storage
        │
        ▼
   FastAPI           ← dashboards + API
```

## Directory layout

```
backend/
├── alembic/              # database migrations
├── app/
│   ├── main.py           # FastAPI application
│   ├── config.py         # pydantic-settings (DATABASE_URL, JWT, OAuth)
│   ├── db/               # async SQLAlchemy session
│   ├── models/           # User, Tenant, Membership, Invite, ingestion entities
│   ├── schemas/          # Pydantic request/response DTOs
│   ├── auth/             # fastapi-users, JWT, OAuth, RBAC dependencies
│   ├── routers/          # auth, tenants, members, invites, connections
│   ├── services/         # tenant + connection domain logic
│   ├── integrations/     # GitHub App auth (JWT → installation token)
│   └── ingestion/        # orchestrator + Meltano runner + CLI
├── meltano/              # taps (tap-github, tap-github-copilot) + target-propel
├── cron/                 # hourly ingestion crontab + wrapper
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```

Entity relationships are documented in [docs/backend/data-model.md](../docs/backend/data-model.md).

## Setup

```bash
cd backend
uv sync
cp ../.env.example ../.env   # set DATABASE_URL, JWT_SECRET, optional OAuth vars
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

The API listens on port `8000` by default.

### Docker dev workflow

Local development uses two Compose services:

| Service | Role | Python env |
|---|---|---|
| `dev` | Editor / shell (where you run tests, migrations, `uv add`) | `backend/.venv` via `uv sync` in `scripts/setup.sh` |
| `backend` | Runs `uvicorn --reload` on port 8000 | `/opt/venv` in the container, synced from bind-mounted `pyproject.toml` + `uv.lock` on start |

Code edits in the `dev` container are picked up by the `backend` service through the `./backend:/app` bind mount. Dependencies are not shared between the two venvs on purpose — the `dev` venv includes test tooling; the `backend` venv is runtime-only.

**Add or change a dependency:**

```bash
cd backend
uv add some-package          # updates pyproject.toml + uv.lock
docker compose restart backend   # entrypoint re-syncs /opt/venv from the lockfile
```

No image rebuild is required for dependency changes. Rebuild only when the Dockerfile itself changes (`docker compose build backend`).

### Migrations

Migrations are applied **automatically on container start** — both locally and
in production — by the image entrypoint running `alembic upgrade head` before
the app boots:

- **Local (`docker compose`):** the `backend` service entrypoint
  ([`backend/entrypoint.sh`](entrypoint.sh)) runs migrations after syncing deps.
  Just `docker compose up` (or `docker compose restart backend`) to apply pending
  migrations.
- **Production (ECS):** the same entrypoint with `SKIP_UV_SYNC=1` runs migrations
  on task start, so every deploy migrates the database before serving traffic.
  `alembic upgrade head` is idempotent, so it is a no-op when already current.

Run them manually when needed:

```bash
cd backend
uv run alembic upgrade head                               # apply migrations
uv run alembic revision --autogenerate -m "description"   # create new migration
# or against a running container:
docker compose exec backend alembic -c /app/alembic.ini upgrade head
```

> Migration safety: during a rolling ECS deploy the new task migrates the shared
> database while the old task still serves the previous schema. Use
> expand/contract migrations (additive first, destructive after old tasks drain)
> to stay backward compatible. If you scale to multiple tasks, they may run
> `upgrade head` concurrently; this is safe when there is nothing to apply, but
> for migrations with heavy DDL consider a dedicated one-off migration task in
> the deploy pipeline instead.

### Local auth

1. Set `JWT_SECRET` in `.env` for local dev (use `openssl rand -hex 32`; the
   default `change-me` is fine when `APP_ENV=development`). In AWS, Terraform
   generates and stores `JWT_SECRET` in Secrets Manager on first apply.
2. Set `AUTH_REGISTRATION_ENABLED=true` to allow email/password signup at the API (off by default).
3. Register via `POST /api/v1/auth/register` with email and password (minimum 8 characters, enforced server-side).
4. Login via `POST /api/v1/auth/login` (form fields `username`, `password`) to receive a JWT.
5. Pass `Authorization: Bearer <token>` on protected routes.

Login and register are rate-limited per client IP (`AUTH_RATE_LIMIT_*` env vars). OAuth providers do not auto-link to existing email/password accounts until email verification is implemented.

Optional Google/GitHub login. Register these provider redirect URLs (under the
**API** origin):

- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/google/callback`
- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/callback` (fastapi-users built-in)
- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/login/callback` (SPA sign in / sign up)
- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/link/callback` (Connect with GitHub on the profile)

`OAUTH_CALLBACK_BASE_URL` is the **API** origin (where the provider returns the
code). The SPA sign-in/link flows then redirect the browser to the **frontend**
origin set by `FRONTEND_BASE_URL` (e.g. `https://app.<zone>` in AWS;
`http://localhost:5173` locally). The two are distinct because the API
(`api.<zone>`) and SPA (`app.<zone>`) are separate origins.

**GitHub credentials** — the login/link client resolves to, in order:

1. `GITHUB_APP_CLIENT_ID` + `GITHUB_APP_CLIENT_SECRET` — **reuse the ingestion
   GitHub App** for user login. These are the App's user-OAuth Client ID
   (`Iv1...`) and a generated client secret, distinct from `GITHUB_APP_ID`
   (numeric, app JWT) and `GITHUB_APP_PRIVATE_KEY`. To use the App for login you
   must, on the GitHub App settings: add the two `github/{login,link}/callback`
   URLs above to the **User authorization callback URL** (GitHub Apps allow
   multiple), generate a **client secret**, and grant **Account permissions →
   Email addresses: Read-only** (needed so first-time sign-up can read the
   user's email when it isn't public).
2. `OAUTH_GITHUB_CLIENT_ID` + `OAUTH_GITHUB_CLIENT_SECRET` — a standalone GitHub
   OAuth app (fallback when the App vars are unset).

### Linear OAuth (data connection)

Linear is a **data source** (not a login provider): a workspace admin connects
their Linear workspace so Propel can ingest issues. It uses the OAuth
authorization-code flow with `actor=app` (the token acts as the Propel app at
the workspace level — the right model for team analytics, vs. `actor=user`).

Create an OAuth application at **Linear → Settings → API → OAuth applications**
(`https://linear.app/settings/api/applications/new`) and configure:

- **Callback URL (redirect URI):**
  `{OAUTH_CALLBACK_BASE_URL}/api/v1/connections/linear/callback`
  (e.g. `https://api.<zone>/api/v1/connections/linear/callback` in AWS,
  `http://localhost:8000/api/v1/connections/linear/callback` locally).
- **Scopes:** `read` (all Propel ingestion needs).
- **Public/Authorize for any workspace:** enable if multiple workspaces will
  connect; otherwise it stays private to your own workspace.

Set the resulting credentials as env (or Secrets Manager) values:

- `OAUTH_LINEAR_CLIENT_ID` — the application's Client ID.
- `OAUTH_LINEAR_CLIENT_SECRET` — the application's Client Secret.
- `TOKEN_ENCRYPTION_KEY` — a Fernet key (`python -c "from cryptography.fernet
  import Fernet; print(Fernet.generate_key().decode())"`) used to encrypt the
  stored access/refresh tokens at rest. Required whenever Linear is enabled.

The connect flow: `GET /api/v1/tenants/{tenant_id}/connections/linear/authorize`
(admin) returns the Linear authorization URL with a signed `state`; the SPA
redirects the browser there; Linear returns to
`…/connections/linear/callback?code&state`, which exchanges the code, reads the
workspace, stores encrypted tokens on a `connected_accounts` row
(`provider='linear'`, `auth_type='oauth'`), and bounces back to
`{FRONTEND_BASE_URL}/settings/workspace?linear=connected`. The Workspace
settings page (admin-only) shows the Linear connection status by polling
`GET /api/v1/tenants/{tenant_id}/connections/linear`.

A Linear **developer token** (`lin_oauth_…`) issued from the app settings is for
local/manual API testing only — it is not part of the production OAuth flow.

### Endpoints

Unversioned (ALB health checks):

| Route | Description |
|---|---|
| `GET /` | Hello World |
| `GET /health` | Health check |

Auth (`/api/v1/auth`):

| Method | Route | Description |
|---|---|---|
| POST | `/register` | Email + password signup |
| POST | `/login` | Email + password sign-in → JWT |
| GET | `/me` | Current user profile |
| GET | `/google/authorize` | Start Google OAuth (when configured) |
| GET | `/google/callback` | Complete Google OAuth |
| GET | `/github/authorize` | Start GitHub OAuth (when configured) |
| GET | `/github/callback` | Complete GitHub OAuth (fastapi-users built-in, JSON) |
| GET | `/github/login/authorize` | Start GitHub sign in / sign up for the SPA |
| GET | `/github/login/callback` | Complete sign-in; redirect to SPA with session token |
| GET | `/github/link/authorize` | Start linking GitHub to the signed-in account |
| GET | `/github/link/callback` | Complete linking; redirect to SPA profile |

Tenants (`/api/v1/tenants`):

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | `/` | authenticated | Create org; creator gets `admin` |
| GET | `/` | authenticated | List user's orgs |
| GET | `/{tenant_id}` | member | Get org details |
| PATCH | `/{tenant_id}` | admin | Update name/slug |
| DELETE | `/{tenant_id}` | admin | Soft-delete org |

Members (`/api/v1/tenants/{tenant_id}/members`):

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/` | member | List members + roles |
| PATCH | `/{user_id}/role` | admin | Assign role |
| DELETE | `/{user_id}` | admin | Remove member |

Invites:

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/tenants/{tenant_id}/invites` | admin/manager | Create invite; returns `invite_url` |
| GET | `/api/v1/tenants/{tenant_id}/invites` | admin/manager | List pending invites |
| DELETE | `/api/v1/tenants/{tenant_id}/invites/{invite_id}` | admin/manager | Revoke invite |
| POST | `/api/v1/invites/{token}/accept` | authenticated | Accept invite |

Connections (`/api/v1/tenants/{tenant_id}/connections`):

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | `/` | admin | List connected accounts |
| GET | `/github/install` | admin | Signed GitHub App install URL |
| GET | `/linear` | member | Linear connection status (`connected`, `workspace_name`) |
| GET | `/linear/authorize` | `connections:manage` | Linear OAuth authorization URL (`actor=app`, `scope=read`) |
| PATCH | `/{connection_id}` | admin | Pause / revoke a connection |
| GET | `/api/v1/connections/github/setup` | authenticated | GitHub App setup callback (binds install to tenant) |
| GET | `/api/v1/connections/linear/callback` | signed state | Linear OAuth callback (binds the workspace to the tenant) |
| POST | `/api/v1/webhooks/github` | HMAC | Install events (`created`/`deleted`/`suspend`) |

### Tests

Tests need a Postgres database named `propel_test`. The host in the connection
string depends on where you run them:

- **From your host machine** (Postgres published by Compose): `localhost`
- **From inside the `dev` container** (Compose network): `postgres`

Create the test database once (works from the host or the `dev` container;
ignore the error if it already exists):

```bash
docker compose exec postgres createdb -U propel propel_test
```

Run the API suite (migrations are applied automatically by the test harness):

```bash
cd backend
uv sync
# Host:
DATABASE_URL=postgresql://propel:propel@localhost:5432/propel_test JWT_SECRET=test-secret uv run pytest
# Inside the dev container, swap localhost -> postgres:
DATABASE_URL=postgresql://propel:propel@postgres:5432/propel_test JWT_SECRET=test-secret uv run pytest
```

Useful flags: `uv run pytest -v` (verbose), `uv run pytest tests/test_connections.py`
(one file), `uv run pytest -k webhook` (by name).

Lint and format locally before pushing (CI enforces both):

```bash
uv run ruff check .
uv run ruff format --check .   # use `ruff format .` to auto-fix
```

The `target-propel` ingestion tests (writers + end-to-end Singer stream) are a
separate suite — see [Testing ingestion](#testing-ingestion) below.

CI runs pytest against a Postgres 18.3 service container (jobs `backend` and
`ingestion-integration`).

### Ingestion (V1 — landing only)

V1 pulls GitHub data and lands it in Postgres as `raw_record` + thin `datapoint`
envelopes. There are **no transforms** at ingest (no dbt, scoring, or analytics);
that is a later layer. The pieces:

- **Extraction:** Meltano `tap-github` (+ custom `tap-github-copilot`) — see
  [`meltano/README.md`](meltano/README.md).
- **Landing:** custom `target-propel` writes `raw_record` and a thin `datapoint`
  envelope with idempotent writes (events dedupe; measurements upsert
  newest-wins).
- **Orchestration:** `app/ingestion` iterates active `connected_accounts`, mints a
  GitHub App installation token, runs the Meltano job, and owns the
  `ingestion_run` lifecycle (with an overlap guard for the hourly cadence). It
  also reaps stale `running` rows at the start of every batch so a killed worker
  can't block ingestion forever.
- **Scheduling:** Dagster, hourly (see below). The Dagster project lives in
  [`../orchestration`](../orchestration).

Run it manually inside the running container (the `backend` and `ingestion`
images bundle Meltano + the taps; plugins install on first container start):

```bash
# Trigger a run on demand (no need to wait for the top of the hour):
docker compose exec ingestion python -m app.ingestion.cli run
docker compose exec ingestion python -m app.ingestion.cli run --job github_commits_sync   # or github_org_sync / github_user_profiles_sync / github_pull_requests_sync / github_issues_sync / copilot_sync
docker compose exec ingestion python -m app.ingestion.cli run --account-id <uuid>
```

You can also trigger `ingestion_job` from the Dagster UI Launchpad at
<http://localhost:3001>.

Beyond activity (PRs, commits, issues), a run also ingests the connected org's
**member roster** (`github_org_sync` → `github_user_profiles_sync`) and links each
GitHub member to a Propel user, auto-provisioning members and mapping GitHub org
owners to Propel admins. See
[`docs/backend/data-model.md`](../docs/backend/data-model.md#github-identity-linking-migration-003)
for the linking rules. This requires the ingestion GitHub App to grant
**Organization permissions → Members: Read-only**.

A run only does work when there's an **active** `connected_accounts` row for a
GitHub App installation. Create one either through the install flow
(`GET /api/v1/tenants/{tenant_id}/connections/github/install` → install the App →
GitHub redirects to the signed `…/connections/github/setup` callback, which binds
the installation to the tenant), or insert a row directly for testing with
`provider='github'`, `auth_type='github_app_installation'`,
`external_account_id=<installation_id>`, `external_account_name=<org login>`,
`status='active'`.

#### Local ingestion credentials (AWS Secrets Manager)

The ingestion GitHub App (separate from the login OAuth app) is configured via
`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_WEBHOOK_SECRET`, and
`GITHUB_APP_SLUG`. Linear OAuth (`OAUTH_LINEAR_CLIENT_ID`, `OAUTH_LINEAR_CLIENT_SECRET`,
`TOKEN_ENCRYPTION_KEY`) uses the same pull path. Rather than passing a private key
around, the shared **dev** credentials live in AWS Secrets Manager under
`propel/dev/ingestion` and are synced with
[`scripts/dev-ingestion-secrets.sh`](../scripts/dev-ingestion-secrets.sh).

**Pull (each developer, after `aws sso login` / configuring credentials):**

```bash
./scripts/dev-ingestion-secrets.sh pull   # writes .env.ingestion.local (gitignored)
docker compose up -d backend ingestion     # both services auto-load that file
```

`.env.ingestion.local` is wired into the `backend` and `ingestion` services
as an optional `env_file`, so the stack still starts for anyone who hasn't pulled
it. The multi-line PEM is stored on one line with `\n` escapes (the app
un-escapes it before signing the App JWT).

**Push (one-time, by whoever owns the dev App — creates or additively updates the secret):**

```bash
export GITHUB_APP_ID=123456
export GITHUB_APP_PRIVATE_KEY_FILE=~/Downloads/propel-dev.private-key.pem
export GITHUB_APP_WEBHOOK_SECRET=...        # optional
export GITHUB_APP_SLUG=propel-dev           # optional
export OAUTH_LINEAR_CLIENT_ID=...           # optional (Linear OAuth)
export OAUTH_LINEAR_CLIENT_SECRET=...       # optional
export TOKEN_ENCRYPTION_KEY=...             # optional (Fernet; generate per dev machine or share dev key)
./scripts/dev-ingestion-secrets.sh push
```

Override the secret name with `PROPEL_DEV_SECRET_ID`, and the AWS account/region
with the standard `AWS_PROFILE` / `AWS_REGION`. Run `… show` to print the current
secret. For a one-off without AWS, you can still set the `GITHUB_APP_*` vars
directly in `.env`.

#### Scheduling — Dagster (hourly)

Dagster is the scheduler. Locally, the `ingestion` Compose service runs the
combined `dagster dev` (webserver + daemon); the daemon fires an hourly schedule
that calls `orchestrator.run_all`:

```bash
docker compose up -d ingestion
docker logs -f propel-ingestion
# Dagster UI: http://localhost:3001
```

In production a dedicated long-running ECS service runs `dagster-daemon` +
`dagster-webserver` from the same image as the API (command `dagster-service`;
see [`entrypoint.sh`](entrypoint.sh)), with the UI published at
`https://dagster.<zone>`. Dagster's own run/event/schedule state shares the app's
Postgres but lives in a dedicated `dagster` schema so its `alembic_version` never
collides with the app's migrations (see
[`../orchestration`](../orchestration)). The legacy `cron/` crontab still ships
in the image as an opt-in fallback (`INGESTION_CRON_ENABLED=1`) but is superseded
by Dagster.

All ingestion logs ship to PostHog under `service.name = propel-ingestion`, so
they can be filtered separately from the API (`propel-backend`).

#### Testing ingestion

| Layer | Where | Runs in |
|---|---|---|
| Envelope mappers (pure) | `tests/test_ingestion_envelopes.py`, `meltano/target-propel/tests/test_envelopes.py` | `backend` job + integration job |
| Datapoint idempotency (DB) | `tests/test_ingestion_idempotency.py` | `backend` job |
| Connections API + webhook | `tests/test_connections.py` | `backend` job |
| Orchestrator lifecycle (Meltano mocked) | `tests/test_ingestion_orchestrator.py` | `backend` job |
| Writers against Postgres | `meltano/target-propel/tests/test_writers.py` | `ingestion-integration` job |
| **End-to-end Singer stream → Postgres** | `meltano/target-propel/tests/test_target_integration.py` | `ingestion-integration` job |

The first four run in the standard `backend` CI job (`uv run pytest`). The
`target-propel` package has its own deps (`singer-sdk`, `psycopg`), so its tests
run in a dedicated **`ingestion-integration`** CI job that migrates a Postgres
service, installs the target, and pipes a real Singer message stream through the
`target-propel` binary to assert landed rows and idempotency.

Run it locally (assumes the `propel_test` database exists — see
[Tests](#tests) for creating it). Unlike the API suite, these tests do **not**
self-migrate, so apply migrations first, and point `PROPEL_DATABASE_URL` at the
same DB (use `localhost` from the host, `postgres` from the `dev` container):

```bash
cd backend
# alembic reads DATABASE_URL; target-propel reads PROPEL_DATABASE_URL — same DB.
export DATABASE_URL=postgresql://propel:propel@localhost:5432/propel_test
export PROPEL_DATABASE_URL=$DATABASE_URL

uv run alembic upgrade head              # migrate the test DB
uv pip install -e meltano/target-propel  # adds singer-sdk + psycopg to the venv
# --no-sync keeps the editable target install from being pruned:
uv run --no-sync pytest meltano/target-propel/tests -v
```

`test_writers.py` and `test_target_integration.py` skip automatically if
`PROPEL_DATABASE_URL` is unset or the ingestion tables are missing, so the suite
degrades gracefully when run without a database.

#### Dagster (scheduler)

Dagster runs as a separate [`../orchestration`](../orchestration) project and a
long-running ECS service. It is the **scheduler only**: it calls the same
`app.ingestion.orchestrator.run_all` entrypoint, while Meltano, the taps, and
`target-propel` stay here unchanged. See the
[orchestration README](../orchestration/README.md) for details.

## Related

- [Data model](../docs/backend/data-model.md) — entity relationships
- [Frontend](../frontend/README.md) — React dashboard
- [Transformation](../transformation/README.md) — dbt SQL transformations
- [Infrastructure](../infrastructure/README.md) — Docker and deployment config
