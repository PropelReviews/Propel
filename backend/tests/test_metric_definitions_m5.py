"""API tests for M5 authoring endpoints (catalog, classify, draft, diff, preview)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from tests.conftest import auth_headers, create_tenant, login_user, register_user

SAMPLE = """
apiVersion: propel/v1
kind: Metric
metadata:
  id: acmem5.sample_count
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


@pytest.mark.asyncio
async def test_m5_catalog_and_classify_and_draft(client: AsyncClient):
    await register_user(client, "m5-admin@example.com")
    token = await login_user(client, "m5-admin@example.com")
    tenant = await create_tenant(client, token, name="Acme M5", slug="acmem5")
    tenant_id = tenant["id"]
    headers = auth_headers(token)

    catalog = await client.get(
        f"/api/v1/tenants/{tenant_id}/metric-catalog",
        headers=headers,
    )
    assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body["catalog_version"] >= 1
    pr = next(e for e in body["entities"] if e["name"] == "pull_request")
    author = next(f for f in pr["fields"] if f["name"] == "author_id")
    assert author["person"] is True

    classify = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions:classify",
        headers=headers,
        json={"yaml": SAMPLE},
    )
    assert classify.status_code == 200, classify.text
    assert classify.json()["kind"] in {"semantic", "non_semantic", "none"}

    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions",
        headers=headers,
        json={"yaml": SAMPLE},
    )
    assert create.status_code == 201, create.text
    version = create.json()["version"]
    revision = create.json()["revision"]

    updated_yaml = SAMPLE.replace("name: Sample", "name: Sample 2")
    put = await client.put(
        f"/api/v1/tenants/{tenant_id}/metric-definitions/draft",
        headers=headers,
        json={
            "yaml": updated_yaml,
            "expected_version": version,
            "expected_revision": revision,
        },
    )
    assert put.status_code == 200, put.text
    assert put.json()["version"] == version
    assert put.json()["revision"] >= revision

    conflict = await client.put(
        f"/api/v1/tenants/{tenant_id}/metric-definitions/draft",
        headers=headers,
        json={
            "yaml": updated_yaml.replace("Sample 2", "Sample 3"),
            "expected_version": version,
            "expected_revision": revision,  # stale
        },
    )
    assert conflict.status_code == 409, conflict.text

    preview = await client.post(
        f"/api/v1/tenants/{tenant_id}/metric-definitions:preview",
        headers=headers,
        json={"yaml": updated_yaml},
    )
    assert preview.status_code == 200, preview.text
    assert "statement_timeout" in preview.json()["sql"]

    health = await client.get(
        f"/api/v1/tenants/{tenant_id}/metric-health",
        headers=headers,
    )
    assert health.status_code == 200, health.text
