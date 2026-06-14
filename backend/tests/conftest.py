import os

# Must be set before app modules load the database engine.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://propel:propel@localhost:5432/propel_test",
)
os.environ.setdefault("APP_ENV", "test")
# CI/local pytest only — not a real encryption key.
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault(
    "TOKEN_ENCRYPTION_KEY",
    "iqHnNRvDhs_n1rp2O6nMgbrerNt1cjcvCkBHg543YVc=",
)

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.main import app

TEST_DATABASE_URL = get_settings().async_database_url

# Use NullPool in tests to avoid asyncpg "another operation is in progress" errors.
import app.db.session as db_session

test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool, echo=False)
db_session.engine = test_engine
db_session.async_session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
engine = test_engine

_ACT_AS_HEADER = "X-Test-Act-As"


class SessionAwareAsyncClient(AsyncClient):
    """AsyncClient that swaps httpOnly session cookies per test user."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_sessions: dict[str, dict[str, str]] = {}

    def save_session(self, user_id: str) -> None:
        cookie_name = get_settings().session_cookie_name
        for cookie in self.cookies.jar:
            if cookie.name == cookie_name:
                self._saved_sessions[user_id] = {cookie_name: cookie.value}
                return

    def _apply_session(self, user_id: str | None) -> None:
        self.cookies.clear()
        if user_id and user_id in self._saved_sessions:
            for name, value in self._saved_sessions[user_id].items():
                self.cookies.set(name, value)

    async def request(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        act_as = headers.pop(_ACT_AS_HEADER, None)
        if act_as is not None:
            self._apply_session(act_as)
        kwargs["headers"] = headers
        return await super().request(method, url, **kwargs)


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter():
    from app.auth.middleware import auth_rate_limiter

    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def apply_migrations():
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(alembic_cfg, "head")
    yield


@pytest.fixture
async def db_engine(apply_migrations):
    yield engine


@pytest.fixture
async def clean_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE external_identities, ingestion_run, datapoint, "
                "raw_record, connected_accounts, tenant_invites, "
                "tenant_role_permissions, tenant_memberships, tenants, "
                "oauth_accounts, users, waitlist_subscribers "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def client(apply_migrations, db_engine, clean_db):
    transport = ASGITransport(app=app)
    async with SessionAwareAsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


async def register_user(
    client: SessionAwareAsyncClient,
    email: str,
    password: str = "testpass123",
    name: str | None = "Test User",
) -> dict:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/test/login",
        params={"email": email},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    client.save_session(body["user_id"])
    return {"id": body["user_id"], "email": body["email"], "name": name}


async def login_user(
    client: SessionAwareAsyncClient,
    email: str,
    password: str = "testpass123",
) -> str:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/test/login",
        params={"email": email},
    )
    assert response.status_code == 200, response.text
    user_id = response.json()["user_id"]
    client.save_session(user_id)
    return user_id


def auth_headers(token: str | None = None) -> dict[str, str]:
    if token:
        return {_ACT_AS_HEADER: token}
    return {}


async def create_tenant(
    client: SessionAwareAsyncClient, token: str, name: str = "Acme", slug: str = "acme"
):
    response = await client.post(
        "/api/v1/tenants/",
        json={"name": name, "slug": slug},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()
