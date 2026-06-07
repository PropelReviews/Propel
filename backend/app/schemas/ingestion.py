"""Read schemas for ingestion observability (the SPA "Data" page).

Read-only views over ingestion_run + datapoint for a tenant. status/kind are
exposed as plain strings to match how the ORM stores them (see models).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connected_account_id: uuid.UUID
    source: str
    resource_type: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
    records_pulled: int
    datapoints_written: int
    error: str | None


class CountByLabel(BaseModel):
    """A single (label, count) pair for a breakdown (by kind, source, etc.)."""

    label: str
    count: int


class IngestionStats(BaseModel):
    total_datapoints: int
    total_raw_records: int
    by_kind: list[CountByLabel]
    by_source: list[CountByLabel]
    last_run_at: datetime | None
