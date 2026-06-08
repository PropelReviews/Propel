"""Dagster code location: the ingestion job + its hourly schedule.

Imported by the webserver and the daemon (see workspace.yaml). Logging is
configured at import time so both processes ship logs to PostHog as
``propel-ingestion``.
"""

from __future__ import annotations

from dagster import Definitions

from propel_orchestration.jobs import ingestion_job, ingestion_schedule
from propel_orchestration.logging import configure_logging

configure_logging()

defs = Definitions(
    jobs=[ingestion_job],
    schedules=[ingestion_schedule],
)
