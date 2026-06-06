"""Unit tests for target-propel envelope mappers (pure, no DB).

The target-propel package lives under backend/meltano; add it to the path so the
landing layer's mapping logic is covered by the backend test suite.
"""

import sys
from pathlib import Path

_TARGET_PROPEL = Path(__file__).resolve().parents[1] / "meltano" / "target-propel"
if str(_TARGET_PROPEL) not in sys.path:
    sys.path.insert(0, str(_TARGET_PROPEL))

from target_propel.envelopes.copilot import map_copilot_record  # noqa: E402
from target_propel.envelopes.github import map_github_record  # noqa: E402


def test_pull_request_maps_to_event_keyed_on_node_id():
    record = {
        "node_id": "PR_kwDO",
        "id": 42,
        "number": 7,
        "state": "open",
        "created_at": "2026-06-01T10:00:00Z",
        "updated_at": "2026-06-02T10:00:00Z",
        "user": {"login": "octocat", "id": 1},
        "org": "acme",
        "repo": "web",
    }
    env = map_github_record("pull_requests", record)

    assert env is not None
    assert env.kind == "event"
    assert env.name == "pull_request"
    assert env.tool == "github"
    assert env.subject_type == "user"
    assert env.subject_id == "octocat"
    assert env.source_key == "PR_kwDO"
    assert env.occurred_at.isoformat() == "2026-06-01T10:00:00+00:00"
    assert env.metadata["repo"] == "acme/web"
    assert env.metadata["number"] == 7


def test_commit_uses_commit_date_and_top_level_author():
    record = {
        "sha": "abc123",
        "node_id": "C_abc",
        "commit": {"author": {"date": "2026-05-30T08:00:00Z"}},
        "author": {"login": "dev1"},
        "org": "acme",
        "repo": "web",
    }
    env = map_github_record("commits", record)

    assert env is not None
    assert env.name == "commit"
    assert env.subject_id == "dev1"
    assert env.source_key == "C_abc"
    assert env.source_id == "abc123"
    assert env.occurred_at.isoformat() == "2026-05-30T08:00:00+00:00"


def test_source_key_falls_back_to_stream_and_id_without_node_id():
    env = map_github_record("issues", {"id": 99, "user": {"login": "x"}})
    assert env is not None
    assert env.source_key == "issue:99"


def test_unmapped_stream_returns_none():
    assert map_github_record("stargazers", {"id": 1}) is None


def test_missing_user_defaults_to_unknown():
    env = map_github_record("commits", {"sha": "s1"})
    assert env is not None
    assert env.subject_id == "unknown"


def test_copilot_record_maps_to_measurement_with_period():
    record = {
        "day": "2026-06-01",
        "user_login": "octocat",
        "org": "acme",
        "code_suggestions": 120,
        "code_acceptances": 40,
    }
    env = map_copilot_record(record)

    assert env is not None
    assert env.kind == "measurement"
    assert env.name == "copilot.usage"
    assert env.tool == "github_copilot"
    assert env.subject_type == "user"
    assert env.subject_id == "octocat"
    assert env.source_key == "octocat:2026-06-01"
    assert env.period_start.isoformat() == "2026-06-01T00:00:00+00:00"
    assert env.period_end.isoformat() == "2026-06-02T00:00:00+00:00"
    # Usage metrics pass through; identity fields are stripped from metadata.
    assert env.metadata["code_suggestions"] == 120
    assert "day" not in env.metadata
    assert "user_login" not in env.metadata


def test_copilot_record_without_user_falls_back_to_org_subject():
    env = map_copilot_record({"date": "2026-06-05", "org": "acme", "total": 3})
    assert env is not None
    assert env.subject_type == "org"
    assert env.subject_id == "acme"
    assert env.source_key == "acme:2026-06-05"
