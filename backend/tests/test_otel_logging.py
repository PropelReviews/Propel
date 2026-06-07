import logging

from app.otel_logging import _OTEL_HANDLER_NAME, setup_logging, shutdown_logging


def test_setup_logging_noop_without_token(monkeypatch):
    monkeypatch.delenv("POSTHOG_TOKEN", raising=False)
    root = logging.getLogger()
    before = list(root.handlers)

    assert setup_logging() is False
    assert root.handlers == before


def test_setup_logging_attaches_handler(monkeypatch):
    monkeypatch.setenv("POSTHOG_TOKEN", "phc_test_token")
    monkeypatch.setenv("POSTHOG_HOST", "https://us.i.posthog.com")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "propel-backend-test")

    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "name", None) == _OTEL_HANDLER_NAME:
            root.removeHandler(handler)

    try:
        assert setup_logging() is True
        assert any(
            getattr(handler, "name", None) == _OTEL_HANDLER_NAME
            for handler in root.handlers
        )
        shutdown_logging()
    finally:
        for handler in list(root.handlers):
            if getattr(handler, "name", None) == _OTEL_HANDLER_NAME:
                root.removeHandler(handler)


def test_setup_logging_idempotent(monkeypatch):
    monkeypatch.setenv("POSTHOG_TOKEN", "phc_test_token")
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "name", None) == _OTEL_HANDLER_NAME:
            root.removeHandler(handler)

    try:
        assert setup_logging() is True
        handler_count = sum(
            1
            for handler in root.handlers
            if getattr(handler, "name", None) == _OTEL_HANDLER_NAME
        )
        assert setup_logging() is True
        assert (
            sum(
                1
                for handler in root.handlers
                if getattr(handler, "name", None) == _OTEL_HANDLER_NAME
            )
            == handler_count
        )
    finally:
        for handler in list(root.handlers):
            if getattr(handler, "name", None) == _OTEL_HANDLER_NAME:
                root.removeHandler(handler)
