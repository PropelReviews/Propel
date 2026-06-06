from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root():
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Hello World"}


def test_cors_preflight_allows_local_dev_origin():
    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_rejects_unlisted_origin():
    with TestClient(app) as client:
        resp = client.options(
            "/api/v1/auth/register",
            headers={
                "Origin": "https://app.beta.propel.ninja",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert resp.status_code == 400
