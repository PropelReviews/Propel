"""Singer RecordSink that lands every tap record.

For each record: append a raw_record, then map a thin datapoint envelope and
upsert it. Streams without an envelope mapping are still landed as raw_record
(audit) but emit no datapoint.
"""

from __future__ import annotations

import os

from singer_sdk.sinks import RecordSink

from target_propel.db import get_connection
from target_propel.envelopes.copilot import COPILOT_STREAM, map_copilot_record
from target_propel.envelopes.github import Envelope, map_github_record
from target_propel.writers import insert_raw_record, upsert_datapoint


def _map_envelope(source: str, stream: str, record: dict) -> Envelope | None:
    if stream == COPILOT_STREAM:
        return map_copilot_record(record)
    # V1 sources are GitHub (events) + GitHub Copilot (measurement, above).
    return map_github_record(stream, record)


class PropelSink(RecordSink):
    """Lands one record per call into raw_record + datapoint."""

    @property
    def _tenant_id(self) -> str:
        value = os.environ.get("PROPEL_TENANT_ID")
        if not value:
            raise RuntimeError("PROPEL_TENANT_ID is not set")
        return value

    @property
    def _source(self) -> str:
        return os.environ.get("PROPEL_SOURCE", "github")

    @property
    def _run_id(self) -> str | None:
        return os.environ.get("PROPEL_RUN_ID")

    def process_record(self, record: dict, context: dict) -> None:
        conn = get_connection()
        with conn.cursor() as cursor:
            raw_id = insert_raw_record(
                cursor,
                tenant_id=self._tenant_id,
                source=self._source,
                resource_type=self.stream_name,
                source_id=_source_id(record),
                payload=record,
                run_id=self._run_id,
            )
            envelope = _map_envelope(self._source, self.stream_name, record)
            if envelope is not None:
                upsert_datapoint(
                    cursor,
                    tenant_id=self._tenant_id,
                    source=self._source,
                    envelope=envelope,
                    raw_record_id=raw_id,
                )


def _source_id(record: dict) -> str | None:
    natural = record.get("node_id") or record.get("id") or record.get("sha")
    return str(natural) if natural is not None else None
