"""API tests for metric definition management."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from tests.conftest import auth_headers, create_tenant, login_user, register_user


@pytest.mark.asyncio
async def test_metric_definitions_list_and_validate(client: AsyncClient):
    await register_user(client, "metrics-admin@example.com")
    token = await login_user(client, "metrics-admin@example.com")
    tenant = await create_tenant(client, token, name="Acme", slug="acmemetrics")
    tenant_id = tenant["id"]
    headers = auth_headers(token)

    yaml_text = """
apiVersion: propel/v1
kind: Metric
metadata:
  id: acmemetrics.sample_count
  name: Sample
  status: draft
  version: 1
spec:
  entity: pull_request
  measure:
    type: count
  filters:
    - field: state
      op: eq
      value: merged
  time:
    field: merged_at
    grains: [day]
  dimensions: []
  visibility: org
"""
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions:validate",
        headers=headers,
        json={"yaml": yaml_text},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True

    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions",
        headers=headers,
        json={"yaml": yaml_text},
    )
    assert create.status_code == 201, create.text
    assert create.json()["metric_id"] == "acmemetrics.sample_count"
    assert create.json()["status"] == "draft"

    activate = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions:activate",
        headers=headers,
        params={"metric_id": "acmemetrics.sample_count"},
        json={},
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "active"

    listing = await client.get(
        f"/api/v1/tenants/{tenant_id}/metric-definitions",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    ids = {row["metric_id"] for row in listing.json()}
    assert "acmemetrics.sample_count" in ids
    assert "propel.merged_prs" in ids


@pytest.mark.asyncio
async def test_metric_definitions_require_auth(client: AsyncClient):
    resp = await client.get(
        "/api/v1/tenants/00000000-0000-0000-0000-000000000000/metric-definitions"
    )
    assert resp.status_code in {401, 403, 404}
