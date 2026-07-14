---
name: propel-backend
description: Conventions and commands for the Propel FastAPI backend — adding endpoints, models, Alembic migrations, auth/multi-tenancy patterns, and running tests. Use when editing anything under backend/ (except backend/meltano/), writing migrations, or working with the API, auth, tenants, or database models.
---

# Propel Backend

FastAPI + SQLAlchemy 2.0 async (asyncpg) + Alembic + fastapi-users. Python 3.12, managed with `uv`. All commands run from `backend/`.

## Commands

```bash
uv run uvicorn app.main:app --reload --port 8000   # or: docker compose up -d backend
uv run ruff check . && uv run ruff format --check . # lint (fix: uv run ruff format .)
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Tests (test DB is propel_test; create once: docker compose exec postgres createdb -U propel propel_test)
DATABASE_URL=postgresql://propel:propel@localhost:5432/propel_test JWT_SECRET=test-secret uv run pytest
```

DB host is `localhost` from the host/dev container, `postgres` inside compose services.

## Layout (`backend/app/`)

- `main.py` — app factory, middleware, router registration (new routers must be registered here)
- `config.py` — pydantic-settings `Settings`, `get_settings()` (lru_cached)
- `db/` — `base.py` (DeclarativeBase), `session.py` (engine + `get_async_session`)
- `models/` — ORM models; **must be exported from `models/__init__.py`** or Alembic autogenerate won't see them. Metric definition store models live in `models/metric_definition.py` (Alembic `013`).
- `schemas/` — Pydantic DTOs: `*Create` / `*Update` / `*Read` (reads use `ConfigDict(from_attributes=True)`)
- `routers/` — thin HTTP layer, prefix `/api/v1/...` (metric definitions: `routers/metric_definitions.py`)
- `services/` — business logic; services own `session.commit()` / `rollback()` and map errors to `HTTPException` (e.g. `IntegrityError` → 409). Definition lifecycle hydrates an in-memory `propel_metrics` store then persists (`services/metric_definitions.py`, `metric_compile.py`).
- Path dependency: `propel-metrics` from `../transformation/propel_metrics` (editable). Dockerfiles copy it to `/transformation/propel_metrics` before `uv sync`.
- `auth/` — fastapi-users, JWT, OAuth, RBAC deps, rate-limit middleware
- `ingestion/` — Meltano orchestrator + CLI (see `propel-data-pipeline` skill)

## Auth & multi-tenancy (critical)

- **No Postgres RLS.** Tenancy is enforced in Python only: every tenant-scoped query must filter by `tenant_id`, and tenant routes must use the deps in `app/auth/dependencies.py` (`require_member`, `require_admin`, `require_invite_manager` → yields `TenantContext(tenant, membership)`).
- Non-members get **404** (not 403) — never reveal a tenant's existence.
- Roles: `admin` / `manager` / `individual` (`Role` Postgres enum); permission matrix in `auth/permissions.py`.
- Metric definition writes use `metrics:manage` (admin default); definition reads use `metrics:read`. Store `org_id` is the tenant **slug** (or `__system` for `propel.*`); no RLS on `metric_definitions`.
- User-only (non-tenant) routes use `Depends(current_active_user)`.
- `oauth_accounts` = sign-in identity; `connected_accounts` = tenant-scoped tool installs (GitHub App). Different things — see `docs/backend/data-model.md`.
- Login is fastapi-users OAuth2 password flow: form-encoded with field `username` (the email).
- Registration is gated by `AUTH_REGISTRATION_ENABLED` env / PostHog flag, fail-closed.

## Adding an endpoint

1. Schemas in `app/schemas/`, model in `app/models/` (export from `__init__.py`).
2. Service in `app/services/<domain>.py` — logic, commits, tenant scoping.
3. Router in `app/routers/<domain>.py` — `APIRouter(prefix="/api/v1/...")`, `response_model=...Read`, explicit status codes (201/204), auth dep.
4. Register the router in `app/main.py`.
5. Tests in `tests/test_<domain>.py` using conftest helpers (`register_user`, `login_user`, `create_tenant`, `auth_headers`). Per-test DB truncation is automatic.

## Models & migrations

- `Mapped[...]` + `mapped_column`, UUID PKs (`default=uuid.uuid4`). Tenant tables: `tenant_id` FK with `ondelete="CASCADE"`.
- Enums: store as **text** for extensible/ingestion fields; Postgres `ENUM` only where established (`Role`). `StrEnum`s live in `models/enums.py`.
- `metadata` is reserved on declarative models — use `meta` (see `ConnectedAccount`).
- Migration revision IDs are sequential numerics with descriptive slugs: `001_initial_auth_and_tenant_models.py`, `002_ingestion_tables.py`, ... Use the next number.
- Always review autogenerate output (partial indexes, server defaults, FK ondelete often need hand-editing — see `002_ingestion_tables.py`).
- Migrations auto-run on container start (`entrypoint.sh`), except where `SKIP_MIGRATIONS=1` (ingestion service). Prefer expand/contract for rolling-deploy safety.

## Gotchas

- After `uv add`, run `docker compose restart backend` (container venv `/opt/venv` is separate from `backend/.venv`).
- In-memory per-IP rate limiter on login/register; tests reset it via an autouse fixture.
- `JWT_SECRET` must be ≥32 chars when `APP_ENV` is production/beta.
- Ingestion integration tests are a separate suite: `uv pip install -e meltano/target-propel`, migrate manually, then `uv run --no-sync pytest meltano/target-propel/tests -v`.
- Dagster keeps its own `dagster` Postgres schema — not managed by Alembic; leave it alone.
- `backend/cron/` is legacy (superseded by Dagster); don't extend it.
