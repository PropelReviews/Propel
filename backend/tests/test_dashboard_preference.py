"""Dashboard preference backup API tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from tests.conftest import (
    auth_headers,
    create_tenant,
    login_user,
    register_user,
)

VALID_LAYOUT = {
    "version": 2,
    "range": "quarter",
    "granularity": "weekly",
    "tiles": [
        {"i": "propel.cycle_time", "x": 0, "y": 0, "w": 6, "h": 4},
        {"i": "propel.merged_prs", "x": 6, "y": 0, "w": 6, "h": 4},
    ],
}


async def _setup(client: AsyncClient, email: str = "dash@example.com"):
    await register_user(client, email)
    token = await login_user(client, email)
    tenant = await create_tenant(client, token)
    return token, tenant


@pytest.mark.asyncio
async def test_dashboard_preference_upsert_and_get(client: AsyncClient):
    token, tenant = await _setup(client)
    path = f"/api/v1/tenants/{tenant['id']}/dashboard-preference"

    missing = await client.get(path, headers=auth_headers(token))
    assert missing.status_code == 404, missing.text

    put = await client.put(
        path, headers=auth_headers(token), json={"layout": VALID_LAYOUT}
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["layout"]["version"] == 2
    assert len(body["layout"]["tiles"]) == 2
    assert "updated_at" in body

    got = await client.get(path, headers=auth_headers(token))
    assert got.status_code == 200, got.text
    assert got.json()["layout"] == body["layout"]

    updated = {
        **VALID_LAYOUT,
        "tiles": [
            {
                "i": "propel.deployment_frequency",
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 5,
            }
        ],
    }
    put2 = await client.put(path, headers=auth_headers(token), json={"layout": updated})
    assert put2.status_code == 200, put2.text
    assert put2.json()["layout"]["tiles"] == updated["tiles"]


@pytest.mark.asyncio
async def test_dashboard_preference_rejects_malformed(client: AsyncClient):
    token, tenant = await _setup(client, email="bad-layout@example.com")
    path = f"/api/v1/tenants/{tenant['id']}/dashboard-preference"

    resp = await client.put(
        path,
        headers=auth_headers(token),
        json={
            "layout": {
                "version": 2,
                "tiles": [
                    {"i": "a", "x": 0, "y": 0, "w": 1, "h": 1},
                    {"i": "a", "x": 1, "y": 0, "w": 1, "h": 1},
                ],
            }
        },
    )
    assert resp.status_code == 422, resp.text

    resp = await client.put(
        path,
        headers=auth_headers(token),
        json={"layout": {"version": 1, "tiles": []}},
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_dashboard_preference_isolation(client: AsyncClient):
    token_a, tenant_a = await _setup(client, email="a@example.com")
    await register_user(client, "b@example.com")
    token_b = await login_user(client, "b@example.com")
    # B joins a different workspace
    tenant_b = await create_tenant(client, token_b, name="Other", slug="other-ws")

    path_a = f"/api/v1/tenants/{tenant_a['id']}/dashboard-preference"
    put = await client.put(
        path_a, headers=auth_headers(token_a), json={"layout": VALID_LAYOUT}
    )
    assert put.status_code == 200, put.text

    # Non-member cannot read another tenant's preference (404).
    outsider = await client.get(path_a, headers=auth_headers(token_b))
    assert outsider.status_code == 404, outsider.text

    # B's own preference starts empty.
    path_b = f"/api/v1/tenants/{tenant_b['id']}/dashboard-preference"
    missing = await client.get(path_b, headers=auth_headers(token_b))
    assert missing.status_code == 404, missing.text
