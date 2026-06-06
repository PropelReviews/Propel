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
│   ├── models/           # User, Tenant, Membership, Invite
│   ├── schemas/          # Pydantic request/response DTOs
│   ├── auth/             # fastapi-users, JWT, OAuth, RBAC dependencies
│   ├── routers/          # auth, tenants, members, invites
│   └── services/         # tenant domain logic
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
  ([`infrastructure/docker/backend-entrypoint.sh`](../infrastructure/docker/backend-entrypoint.sh))
  runs migrations after syncing deps. Just `docker compose up` (or
  `docker compose restart backend`) to apply pending migrations.
- **Production (ECS):** the prod image entrypoint
  ([`backend/docker-entrypoint.sh`](docker-entrypoint.sh)) runs migrations on
  task start, so every deploy migrates the database before serving traffic.
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

1. Set `JWT_SECRET` in `.env` (use a strong random value in production).
2. Register via `POST /api/v1/auth/register` with email and password.
3. Login via `POST /api/v1/auth/login` (form fields `username`, `password`) to receive a JWT.
4. Pass `Authorization: Bearer <token>` on protected routes.

Optional Google/GitHub login: set `OAUTH_*` client IDs/secrets and register redirect URLs:

- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/google/callback`
- `{OAUTH_CALLBACK_BASE_URL}/api/v1/auth/github/callback`

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
| GET | `/github/callback` | Complete GitHub OAuth |

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

Future (v2, not implemented): `/api/v1/tenants/{tenant_id}/connections` for tool OAuth tokens.

### Tests

```bash
cd backend
uv sync
DATABASE_URL=postgresql://propel:propel@localhost:5432/propel_test uv run pytest
```

CI runs pytest against a Postgres 16 service container.

### Extraction (coming soon)

```bash
# From meltano/
meltano run tap-github target-postgres
```

## Related

- [Data model](../docs/backend/data-model.md) — entity relationships
- [Frontend](../frontend/README.md) — React dashboard
- [Transformation](../transformation/README.md) — dbt SQL transformations
- [Infrastructure](../infrastructure/README.md) — Docker and deployment config
