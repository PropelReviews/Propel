"""Logging setup for the Dagster ingestion service.

Stdout for run logs is configured in ``dagster.yaml`` (``python_logs`` with a
stdout ``StreamHandler`` and ``managed_python_loggers: [propel]``). This module
attaches the backend's OTLP-to-PostHog handler (``app.otel_logging``) so
ingestion logs also land in PostHog under ``service.name = propel-ingestion``,
filterable separately from the API (``propel-backend``). Safe to call repeatedly;
a no-op once configured and when PostHog isn't set up.
"""

from __future__ import annotations

import logging
import os

_INGESTION_SERVICE_NAME = "propel-ingestion"
_configured = False


def configure_logging() -> None:
    """Attach the OTLP handler for the ingestion service (idempotent)."""
    global _configured
    if _configured:
        return

    # Default the service name so OTLP logs are filterable as `propel-ingestion`,
    # while still allowing an explicit override from the environment.
    os.environ.setdefault("OTEL_SERVICE_NAME", _INGESTION_SERVICE_NAME)

    try:
        from app.otel_logging import setup_logging

        setup_logging()
    except Exception:  # noqa: BLE001 — never let logging setup crash the service
        logging.getLogger("propel.ingestion.dagster").warning(
            "OTLP logging setup failed; continuing with stdout only",
            exc_info=True,
        )

    # Ensure the ingestion loggers propagate at INFO to the root OTLP handler.
    logging.getLogger("propel").setLevel(logging.INFO)
    _configured = True
