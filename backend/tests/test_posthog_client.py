"""Unit tests for the shared PostHog client setup."""

import sys
import types
from types import SimpleNamespace

import pytest

import app.posthog_client as pc


@pytest.fixture(autouse=True)
def _reset_client():
    """Each test starts and ends with no initialised client."""
    pc._client = None
    yield
    pc._client = None


def _fake_settings(**overrides):
    base = {
        "posthog_token": "phc_test",
        "posthog_host": "https://us.i.posthog.com",
        "posthog_personal_api_key": "phx_test",
        "app_env": "test",
        "app_version": "9.9.9",
        "git_sha": "abc123",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _install_fake_posthog(monkeypatch):
    """Replace the ``posthog`` import with a stub that records constructor kwargs."""
    captured = {}

    class _FakePosthog:
        def __init__(self, project_api_key, **kwargs):
            captured["project_api_key"] = project_api_key
            captured.update(kwargs)

        def shutdown(self):
            captured["shutdown"] = True

    module = types.ModuleType("posthog")
    module.Posthog = _FakePosthog
    monkeypatch.setitem(sys.modules, "posthog", module)
    return captured


def test_init_noop_when_token_unset(monkeypatch):
    monkeypatch.setattr(pc, "get_settings", lambda: _fake_settings(posthog_token=""))
    pc.init_posthog(service_name="propel-backend")
    assert pc.get_client() is None


def test_init_passes_release_and_in_app_modules(monkeypatch):
    monkeypatch.setattr(pc, "get_settings", lambda: _fake_settings())
    captured = _install_fake_posthog(monkeypatch)

    pc.init_posthog(
        service_name="propel-ingestion",
        in_app_modules=["app", "propel_orchestration"],
    )

    assert pc.get_client() is not None
    assert captured["enable_exception_autocapture"] is True
    assert captured["in_app_modules"] == ["app", "propel_orchestration"]
    assert captured["super_properties"] == {
        "app_environment": "test",
        "app_version": "9.9.9",
        "git_sha": "abc123",
        "service": "propel-ingestion",
    }


def test_init_is_idempotent(monkeypatch):
    monkeypatch.setattr(pc, "get_settings", lambda: _fake_settings())
    _install_fake_posthog(monkeypatch)

    pc.init_posthog(service_name="propel-backend")
    first = pc.get_client()
    pc.init_posthog(service_name="propel-backend")
    assert pc.get_client() is first


def test_project_root_prefers_container_path(monkeypatch):
    monkeypatch.setattr(pc.os.path, "isdir", lambda path: path == "/app")
    assert pc._project_root() == "/app"


def test_project_root_falls_back_to_repo_root(monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(pc.os.path, "isdir", lambda path: False)
    # backend/app/posthog_client.py -> repo root is three parents up.
    expected = str(Path(pc.__file__).resolve().parents[2])
    assert pc._project_root() == expected


def test_shutdown_clears_client(monkeypatch):
    monkeypatch.setattr(pc, "get_settings", lambda: _fake_settings())
    _install_fake_posthog(monkeypatch)

    pc.init_posthog(service_name="propel-backend")
    assert pc.get_client() is not None
    pc.shutdown_posthog()
    assert pc.get_client() is None
