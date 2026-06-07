"""Append-only writer for raw_record (ingestion spec §4).

The immutable provider payload as fetched. Never deduped or updated here.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

RAW_RECORD_INSERT = """
    INSERT INTO raw_record
        (id, tenant_id, source, resource_type, source_id, payload, run_id)
    VALUES
        (%(id)s, %(tenant_id)s, %(source)s, %(resource_type)s, %(source_id)s,
         %(payload)s, %(run_id)s)
    RETURNING id
"""


def insert_raw_record(
    cursor: Any,
    *,
    tenant_id: str,
    source: str,
    resource_type: str,
    source_id: str | None,
    payload: dict,
    run_id: str | None,
) -> uuid.UUID:
    record_id = uuid.uuid4()
    cursor.execute(
        RAW_RECORD_INSERT,
        {
            "id": record_id,
            "tenant_id": tenant_id,
            "source": source,
            "resource_type": resource_type,
            "source_id": source_id,
            "payload": json.dumps(payload, default=str),
            "run_id": run_id,
        },
    )
    return record_id
