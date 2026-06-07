import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from tests.conftest import (
    auth_headers,
    create_tenant,
    login_user,
    register_user,
)

from app.db.session import async_session_maker
from app.models.connected_account import ConnectedAccount
from app.models.datapoint import Datapoint
from app.models.ingestion_run import IngestionRun


async def _seed_account(tenant_id: uuid.UUID) -> uuid.UUID:
    async with async_session_maker() as session:
        account = ConnectedAccount(
            tenant_id=tenant_id,
            provider="github",
            auth_type="github_app_installation",
            external_account_id="999",
            external_account_name="acme",
            status="active",
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account.id


async def _seed_run(
    tenant_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    status: str = "success",
    records: int = 10,
    datapoints: int = 8,
) -> None:
    async with async_session_maker() as session:
        session.add(
            IngestionRun(
                tenant_id=tenant_id,
                connected_account_id=account_id,
                source="github",
                resource_type="github",
                status=status,
                records_pulled=records,
                datapoints_written=datapoints,
                finished_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _seed_datapoint(
    tenant_id: uuid.UUID, *, kind: str, source: str, source_key: str
) -> None:
    async with async_session_maker() as session:
        session.add(
            Datapoint(
                tenant_id=tenant_id,
                source=source,
                tool=source,
                kind=kind,
                name="pull_request.opened",
                subject_type="pull_request",
                subject_id="pr-1",
                occurred_at=datetime.now(UTC),
                source_key=source_key,
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_list_ingestion_runs(client: AsyncClient):
    await register_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)
    tenant_id = uuid.UUID(tenant["id"])

    account_id = await _seed_account(tenant_id)
    await _seed_run(tenant_id, account_id, status="success")
    await _seed_run(tenant_id, account_id, status="error")

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/ingestion/runs",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    runs = resp.json()
    assert len(runs) == 2
    statuses = {r["status"] for r in runs}
    assert statuses == {"success", "error"}
    # Most recent first, and the response model shape is present.
    first = runs[0]
    assert {"records_pulled", "datapoints_written", "started_at"} <= first.keys()


@pytest.mark.asyncio
async def test_ingestion_stats(client: AsyncClient):
    await register_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_datapoint(tenant_id, kind="event", source="github", source_key="a")
    await _seed_datapoint(tenant_id, kind="event", source="github", source_key="b")
    await _seed_datapoint(
        tenant_id, kind="measurement", source="github", source_key="c"
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/ingestion/stats",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    stats = resp.json()
    assert stats["total_datapoints"] == 3
    by_kind = {row["label"]: row["count"] for row in stats["by_kind"]}
    assert by_kind == {"event": 2, "measurement": 1}
    by_source = {row["label"]: row["count"] for row in stats["by_source"]}
    assert by_source == {"github": 3}


@pytest.mark.asyncio
async def test_ingestion_endpoints_are_tenant_scoped(client: AsyncClient):
    # A user with no membership in the tenant gets 404 (require_member).
    await register_user(client, "owner@example.com")
    owner_token = await login_user(client, "owner@example.com")
    tenant = await create_tenant(client, owner_token)

    await register_user(client, "outsider@example.com")
    outsider_token = await login_user(client, "outsider@example.com")

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/ingestion/runs",
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingestion_endpoints_require_auth(client: AsyncClient):
    await register_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)

    resp = await client.get(f"/api/v1/tenants/{tenant['id']}/ingestion/stats")
    assert resp.status_code == 401
