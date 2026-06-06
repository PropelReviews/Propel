import os

# Must be set before app modules load the database engine.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://propel:propel@localhost:5432/propel_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret")

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
                "TRUNCATE tenant_invites, tenant_memberships, tenants, "
                "oauth_accounts, users RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
async def client(apply_migrations, db_engine, clean_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register_user(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
    name: str | None = "Test User",
) -> dict:
    payload = {"email": email, "password": password}
    if name is not None:
        payload["name"] = name
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def login_user(
    client: AsyncClient,
    email: str,
    password: str = "testpass123",
) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_tenant(client: AsyncClient, token: str, name: str = "Acme", slug: str = "acme"):
    response = await client.post(
        "/api/v1/tenants/",
        json={"name": name, "slug": slug},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()
