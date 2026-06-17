"""Unit tests for the server-side feature-flag evaluation policy."""

import app.feature_flags as ff


class _FakeClient:
    def __init__(self, result):
        self._result = result

    def feature_enabled(self, key, distinct_id):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _use_client(monkeypatch, client):
    """Point feature_flags at a fake shared client."""
    monkeypatch.setattr(ff, "get_client", lambda: client)


def test_unconfigured_falls_back_to_default(monkeypatch):
    # No PostHog client -> the static default governs (local/dev/test).
    _use_client(monkeypatch, None)
    assert ff.is_enabled("any-flag", "ip", default=True) is True
    assert ff.is_enabled("any-flag", "ip", default=False) is False


def test_configured_uses_flag_value(monkeypatch):
    _use_client(monkeypatch, _FakeClient(True))
    assert ff.is_enabled("flag", "ip", default=False) is True

    _use_client(monkeypatch, _FakeClient(False))
    assert ff.is_enabled("flag", "ip", default=True) is False


def test_configured_fails_closed_on_missing_flag(monkeypatch):
    # Flag not found -> feature_enabled returns None -> blocked, despite default.
    _use_client(monkeypatch, _FakeClient(None))
    assert ff.is_enabled("flag", "ip", default=True) is False


def test_configured_fails_closed_on_error(monkeypatch):
    _use_client(monkeypatch, _FakeClient(RuntimeError("boom")))
    assert ff.is_enabled("flag", "ip", default=True) is False
