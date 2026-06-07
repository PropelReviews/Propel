"""Structured logging helpers for the ingestion CLI and Dagster ops."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.otel_logging import setup_logging, shutdown_logging

# Standard LogRecord attributes — everything else is treated as structured fields.
_RECORD_STD_KEYS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line for container stdout."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RECORD_STD_KEYS and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_ingestion_logging(*, service_name: str | None = None) -> bool:
    """Configure JSON stdout logging and optional PostHog OTLP export."""
    if service_name:
        import os

        os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

    root = logging.getLogger()
    if not any(isinstance(handler, logging.StreamHandler) for handler in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)

    logging.getLogger("propel").setLevel(logging.INFO)
    logging.getLogger("propel.ingestion").setLevel(logging.INFO)
    if root.level == logging.WARNING:
        root.setLevel(logging.INFO)

    return setup_logging()


def shutdown_ingestion_logging(otel_enabled: bool) -> None:
    if otel_enabled:
        shutdown_logging()
