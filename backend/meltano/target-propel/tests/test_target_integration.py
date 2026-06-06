"""End-to-end Singer-protocol integration test.

Pipes a real Singer message stream (SCHEMA + RECORD lines, exactly what a tap
emits) through the `target-propel` binary and asserts the rows land in Postgres
with the right envelope and idempotency behavior. This exercises the full
landing path — CLI, sink, envelope mappers, writers, DB constraints — not just
the pieces in isolation.

Skipped unless singer-sdk + psycopg are installed and PROPEL_DATABASE_URL points
at a database migrated to the ingestion schema (the CI `ingestion-integration`
job sets both up).
"""

import json
import os
import subprocess
import sys
import uuid

import pytest

pytest.importorskip("singer_sdk")
psycopg = pytest.importorskip("psycopg")

if not os.environ.get("PROPEL_DATABASE_URL"):
    pytest.skip("PROPEL_DATABASE_URL not set", allow_module_level=True)

from target_propel.db import _normalize_dsn  # noqa: E402

_PERMISSIVE_SCHEMA = {"type": "object", "additionalProperties": True, "properties": {}}


def _dsn() -> str:
    return _normalize_dsn(os.environ["PROPEL_DATABASE_URL"])


def _tables_exist() -> bool:
    with psycopg.connect(_dsn(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.datapoint')")
        return cur.fetchone()[0] is not None


if not _tables_exist():
    pytest.skip(
        "ingestion tables not migrated; run `alembic upgrade head`",
        allow_module_level=True,
    )


def _singer_stream() -> str:
    pr_record = {
        "id": 1,
        "node_id": "PR_int_1",
        "number": 5,
        "state": "open",
        "created_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z",
        "user": {"login": "octocat"},
        "org": "acme",
        "repo": "web",
    }
    copilot_record = {"day": "2026-06-01", "user_login": "octocat", "suggestions": 10}
    messages = [
        {
            "type": "SCHEMA",
            "stream": "pull_requests",
            "schema": _PERMISSIVE_SCHEMA,
            "key_properties": ["id"],
        },
        {"type": "RECORD", "stream": "pull_requests", "record": pr_record},
        {
            "type": "SCHEMA",
            "stream": "copilot_usage",
            "schema": _PERMISSIVE_SCHEMA,
            "key_properties": ["day"],
        },
        {"type": "RECORD", "stream": "copilot_usage", "record": copilot_record},
    ]
    return "\n".join(json.dumps(m) for m in messages) + "\n"


def _run_target(tmp_path, tenant_id: str, run_id: str) -> subprocess.CompletedProcess:
    config = tmp_path / "config.json"
    config.write_text("{}")
    env = {
        **os.environ,
        "PROPEL_TENANT_ID": tenant_id,
        "PROPEL_CONNECTED_ACCOUNT_ID": str(uuid.uuid4()),
        "PROPEL_RUN_ID": run_id,
        "PROPEL_SOURCE": "github",
    }
    return subprocess.run(
        [sys.executable, "-m", "target_propel.target", "--config", str(config)],
        input=_singer_stream(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture
def tenant_id():
    tid = str(uuid.uuid4())
    yield tid
    with psycopg.connect(_dsn(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM datapoint WHERE tenant_id = %s", (tid,))
        cur.execute("DELETE FROM raw_record WHERE tenant_id = %s", (tid,))


def test_stream_lands_raw_records_and_datapoints(tmp_path, tenant_id):
    run_id = str(uuid.uuid4())
    result = _run_target(tmp_path, tenant_id, run_id)
    assert result.returncode == 0, f"target failed:\n{result.stderr}"

    with psycopg.connect(_dsn(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM raw_record WHERE tenant_id = %s", (tenant_id,)
        )
        assert cur.fetchone()[0] == 2

        cur.execute(
            "SELECT name, subject_id, source_key FROM datapoint "
            "WHERE tenant_id = %s AND kind = 'event'",
            (tenant_id,),
        )
        event = cur.fetchone()
        assert event == ("pull_request", "octocat", "PR_int_1")

        cur.execute(
            "SELECT tool, name, period_start IS NOT NULL FROM datapoint "
            "WHERE tenant_id = %s AND kind = 'measurement'",
            (tenant_id,),
        )
        measurement = cur.fetchone()
        assert measurement == ("github_copilot", "copilot.usage", True)

        # raw_record carries lineage back to the run.
        cur.execute("SELECT count(*) FROM raw_record WHERE run_id = %s", (run_id,))
        assert cur.fetchone()[0] == 2


def test_event_landing_is_idempotent_across_runs(tmp_path, tenant_id):
    first = _run_target(tmp_path, tenant_id, str(uuid.uuid4()))
    second = _run_target(tmp_path, tenant_id, str(uuid.uuid4()))
    assert first.returncode == 0 and second.returncode == 0

    with psycopg.connect(_dsn(), autocommit=True) as conn, conn.cursor() as cur:
        # raw_record is append-only: two runs -> four rows.
        cur.execute(
            "SELECT count(*) FROM raw_record WHERE tenant_id = %s", (tenant_id,)
        )
        assert cur.fetchone()[0] == 4

        # datapoint dedupes: one event + one measurement regardless of re-runs.
        cur.execute(
            "SELECT kind, count(*) FROM datapoint WHERE tenant_id = %s GROUP BY kind",
            (tenant_id,),
        )
        counts = dict(cur.fetchall())
        assert counts == {"event": 1, "measurement": 1}
