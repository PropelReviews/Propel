"""Copilot metrics availability probe maps GitHub responses to a bool."""

import httpx
import pytest

from app.integrations.github import copilot

_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _patch_response(monkeypatch, status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=[])

    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return _REAL_ASYNC_CLIENT(transport=transport)

    monkeypatch.setattr(copilot.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_probe_returns_true_on_200(monkeypatch):
    _patch_response(monkeypatch, 200)
    assert await copilot.copilot_metrics_available("tok", "acme") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [404, 403, 422])
async def test_probe_returns_false_when_copilot_unavailable(monkeypatch, status_code):
    _patch_response(monkeypatch, status_code)
    assert await copilot.copilot_metrics_available("tok", "acme") is False


@pytest.mark.asyncio
async def test_probe_returns_false_on_server_error(monkeypatch):
    _patch_response(monkeypatch, 500)
    assert await copilot.copilot_metrics_available("tok", "acme") is False


@pytest.mark.asyncio
async def test_probe_returns_false_on_network_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return _REAL_ASYNC_CLIENT(transport=transport)

    monkeypatch.setattr(copilot.httpx, "AsyncClient", factory)
    assert await copilot.copilot_metrics_available("tok", "acme") is False
