"""Idempotent writer for datapoint (ingestion spec §6).

Events are append-and-dedupe: ON CONFLICT DO NOTHING on the partial unique
index. Measurements are restated: ON CONFLICT DO UPDATE, but only when the
incoming observed_at is newer — this is what stops the double-count when GitHub
republishes a day.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from target_propel.envelopes.github import Envelope

_EVENT_INSERT = """
    INSERT INTO datapoint
        (id, tenant_id, source, tool, kind, name, subject_type, subject_id,
         occurred_at, period_start, period_end, source_key, metadata,
         raw_record_id, observed_at)
    VALUES
        (%(id)s, %(tenant_id)s, %(source)s, %(tool)s, 'event', %(name)s,
         %(subject_type)s, %(subject_id)s, %(occurred_at)s, NULL, NULL,
         %(source_key)s, %(metadata)s, %(raw_record_id)s, %(observed_at)s)
    ON CONFLICT (tenant_id, source, source_key) WHERE kind = 'event'
    DO NOTHING
    RETURNING id
"""

_MEASUREMENT_UPSERT = """
    INSERT INTO datapoint
        (id, tenant_id, source, tool, kind, name, subject_type, subject_id,
         occurred_at, period_start, period_end, source_key, metadata,
         raw_record_id, observed_at)
    VALUES
        (%(id)s, %(tenant_id)s, %(source)s, %(tool)s, 'measurement', %(name)s,
         %(subject_type)s, %(subject_id)s, %(occurred_at)s, %(period_start)s,
         %(period_end)s, %(source_key)s, %(metadata)s, %(raw_record_id)s,
         %(observed_at)s)
    ON CONFLICT (tenant_id, tool, name, subject_id, period_start)
        WHERE kind = 'measurement'
    DO UPDATE SET
        observed_at = EXCLUDED.observed_at,
        occurred_at = EXCLUDED.occurred_at,
        period_end = EXCLUDED.period_end,
        metadata = EXCLUDED.metadata,
        raw_record_id = EXCLUDED.raw_record_id
    WHERE datapoint.observed_at < EXCLUDED.observed_at
    RETURNING id
"""


def upsert_datapoint(
    cursor: Any,
    *,
    tenant_id: str,
    source: str,
    envelope: Envelope,
    raw_record_id: uuid.UUID | None,
    observed_at: datetime | None = None,
) -> bool:
    """Write a datapoint. Returns True if a row was inserted/updated, else False."""
    params = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "source": source,
        "tool": envelope.tool,
        "name": envelope.name,
        "subject_type": envelope.subject_type,
        "subject_id": envelope.subject_id,
        "occurred_at": envelope.occurred_at,
        "period_start": envelope.period_start,
        "period_end": envelope.period_end,
        "source_key": envelope.source_key,
        "metadata": json.dumps(envelope.metadata, default=str),
        "raw_record_id": raw_record_id,
        "observed_at": observed_at,
    }
    sql = _MEASUREMENT_UPSERT if envelope.kind == "measurement" else _EVENT_INSERT
    if observed_at is None:
        # Let the DB default (now()) apply for events; measurements need a value
        # for the newest-wins comparison, so fall back to now() explicitly.
        params["observed_at"] = datetime.now(envelope.occurred_at.tzinfo)
    cursor.execute(sql, params)
    return cursor.fetchone() is not None
