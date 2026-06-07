"""OpenTelemetry log export to PostHog.

PostHog ingests standard OTLP/HTTP logs at ``<host>/i/v1/logs``, authenticated
with the project token as a bearer header. The handler is attached to the root
logger so existing ``logging.getLogger(...)`` calls are exported unchanged.

Logging degrades gracefully:
- a no-op when ``POSTHOG_TOKEN`` is unset, and
- a no-op when the OpenTelemetry packages are not installed.
"""

from __future__ import annotations

import logging
import os

_OTEL_HANDLER_NAME = "posthog-otlp"


def _otel_resource(service_name: str):
    from opentelemetry.sdk.resources import Resource

    return Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": os.getenv("APP_ENV", "development"),
        }
    )


def setup_logging() -> bool:
    """Attach an OTLP log handler to the root logger. Returns True when enabled."""
    token = os.getenv("POSTHOG_TOKEN")
    if not token:
        return False

    root = logging.getLogger()
    if any(
        getattr(handler, "name", None) == _OTEL_HANDLER_NAME
        for handler in root.handlers
    ):
        return True

    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        return False

    host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com").rstrip("/")
    service_name = os.getenv("OTEL_SERVICE_NAME", "propel-backend")

    provider = LoggerProvider(resource=_otel_resource(service_name))
    exporter = OTLPLogExporter(
        endpoint=f"{host}/i/v1/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=provider)
    handler.name = _OTEL_HANDLER_NAME
    root.addHandler(handler)

    # Ensure app loggers reach the root handler without replacing uvicorn output.
    logging.getLogger("propel").setLevel(logging.INFO)
    if root.level == logging.WARNING:
        root.setLevel(logging.INFO)

    return True


def shutdown_logging() -> None:
    """Flush queued log records on application shutdown."""
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, "name", None) != _OTEL_HANDLER_NAME:
            continue
        flush = getattr(handler, "flush", None)
        if callable(flush):
            flush()
        shutdown = getattr(handler, "shutdown", None)
        if callable(shutdown):
            shutdown()
