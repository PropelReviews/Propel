"""Writer idempotency tests against a real Postgres.

Skipped unless psycopg is installed and PROPEL_DATABASE_URL points at a database
migrated to the ingestion schema. Run with:

    PROPEL_DATABASE_URL=postgresql://propel:propel@localhost:5432/propel \
        cd target-propel && pytest
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

psycopg = pytest.importorskip("psycopg")

if not os.environ.get("PROPEL_DATABASE_URL"):
    pytest.skip("PROPEL_DATABASE_URL not set", allow_module_level=True)

from target_propel.db import _normalize_dsn  # noqa: E402
from target_propel.envelopes.copilot import map_copilot_record  # noqa: E402
from target_propel.envelopes.github import map_github_record  # noqa: E402
from target_propel.writers import insert_raw_record, upsert_datapoint  # noqa: E402


@pytest.fixture
def conn():
    connection = psycopg.connect(
        _normalize_dsn(os.environ["PROPEL_DATABASE_URL"]), autocommit=True
    )
    yield connection
    connection.close()


@pytest.fixture
def tenant_id(conn):
    tid = str(uuid.uuid4())
    yield tid
    with conn.cursor() as cur:
        cur.execute("DELETE FROM datapoint WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM raw_record WHERE tenant_id = %s", (tid,))


def test_event_is_idempotent(conn, tenant_id):
    record = {
        "node_id": "PR_node_1",
        "number": 1,
        "created_at": "2026-06-01T00:00:00Z",
        "user": {"login": "octocat"},
        "org": "acme",
        "repo": "web",
    }
    envelope = map_github_record("pull_requests", record)
    for _ in range(2):
        with conn.cursor() as cur:
            raw_id = insert_raw_record(
                cur,
                tenant_id=tenant_id,
                source="github",
                resource_type="pull_requests",
                source_id="PR_node_1",
                payload=record,
                run_id=None,
            )
            upsert_datapoint(
                cur,
                tenant_id=tenant_id,
                source="github",
                envelope=envelope,
                raw_record_id=raw_id,
            )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM datapoint WHERE tenant_id = %s AND kind='event'",
            (tenant_id,),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT count(*) FROM raw_record WHERE tenant_id = %s", (tenant_id,)
        )
        # raw_record is append-only: both fetches are retained.
        assert cur.fetchone()[0] == 2


def test_measurement_restatement_keeps_newest(conn, tenant_id):
    record = {"day": "2026-06-01", "user_login": "octocat", "v": 1}
    envelope = map_copilot_record(record)
    now = datetime.now(UTC)
    with conn.cursor() as cur:
        upsert_datapoint(
            cur,
            tenant_id=tenant_id,
            source="github",
            envelope=envelope,
            raw_record_id=None,
            observed_at=now,
        )
    newer = map_copilot_record({"day": "2026-06-01", "user_login": "octocat", "v": 2})
    with conn.cursor() as cur:
        upsert_datapoint(
            cur,
            tenant_id=tenant_id,
            source="github",
            envelope=newer,
            raw_record_id=None,
            observed_at=now + timedelta(days=1),
        )
    older = map_copilot_record({"day": "2026-06-01", "user_login": "octocat", "v": 9})
    with conn.cursor() as cur:
        upsert_datapoint(
            cur,
            tenant_id=tenant_id,
            source="github",
            envelope=older,
            raw_record_id=None,
            observed_at=now - timedelta(days=1),
        )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT metadata->>'v' FROM datapoint "
            "WHERE tenant_id = %s AND kind='measurement'",
            (tenant_id,),
        )
        assert cur.fetchone()[0] == "2"
