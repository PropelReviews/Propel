"""Pure envelope-mapper tests. Run with: cd target-propel && pytest."""

from target_propel.envelopes.copilot import map_copilot_record
from target_propel.envelopes.github import map_github_record


def test_pull_request_event():
    env = map_github_record(
        "pull_requests",
        {
            "node_id": "PR_1",
            "number": 3,
            "created_at": "2026-06-01T10:00:00Z",
            "user": {"login": "octocat"},
            "org": "acme",
            "repo": "web",
        },
    )
    assert env.kind == "event"
    assert env.name == "pull_request"
    assert env.source_key == "PR_1"
    assert env.subject_id == "octocat"
    assert env.metadata["repo"] == "acme/web"


def test_unmapped_stream_is_skipped():
    assert map_github_record("workflow_runs", {"id": 1}) is None


def test_copilot_measurement():
    env = map_copilot_record(
        {"day": "2026-06-01", "user_login": "octocat", "suggestions": 10}
    )
    assert env.kind == "measurement"
    assert env.tool == "github_copilot"
    assert env.source_key == "octocat:2026-06-01"
    assert env.period_end is not None
    assert env.metadata["suggestions"] == 10
