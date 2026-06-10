import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_join_waitlist(client: AsyncClient):
    response = await client.post(
        "/api/v1/waitlist", json={"email": "Early.Bird@Example.com"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "early.bird@example.com"
    assert body["id"]
    assert body["created_at"]


@pytest.mark.asyncio
async def test_join_waitlist_duplicate_email_conflicts(client: AsyncClient):
    response = await client.post("/api/v1/waitlist", json={"email": "dup@example.com"})
    assert response.status_code == 201, response.text

    # Same email, different casing — normalized to lowercase, so a duplicate.
    response = await client.post("/api/v1/waitlist", json={"email": "DUP@example.com"})
    assert response.status_code == 409
    assert response.json()["detail"] == "WAITLIST_EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_join_waitlist_invalid_email(client: AsyncClient):
    response = await client.post("/api/v1/waitlist", json={"email": "not-an-email"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_join_waitlist_rate_limited(client: AsyncClient, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 3)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)

    for i in range(3):
        response = await client.post(
            "/api/v1/waitlist", json={"email": f"burst{i}@example.com"}
        )
        assert response.status_code == 201, response.text

    response = await client.post(
        "/api/v1/waitlist", json={"email": "burst3@example.com"}
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "TOO_MANY_REQUESTS"
