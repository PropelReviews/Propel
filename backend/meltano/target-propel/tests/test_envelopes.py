"""Pure envelope-mapper tests. Run with: cd target-propel && pytest."""

from target_propel.envelopes.copilot import map_copilot_record
from target_propel.envelopes.github import map_github_record
from target_propel.envelopes.linear import map_linear_record


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


def test_linear_issue_event():
    env = map_linear_record(
        "issues",
        {
            "id": "issue-uuid-1",
            "identifier": "ENG-42",
            "title": "Fix the thing",
            "createdAt": "2026-06-01T10:00:00Z",
            "state": {"name": "In Progress", "type": "started"},
            "team": {"key": "ENG"},
            "assignee": {"id": "user-uuid-1", "email": "dev@acme.com"},
            "creator": {"id": "user-uuid-2"},
        },
    )
    assert env.kind == "event"
    assert env.name == "issue"
    assert env.tool == "linear"
    assert env.subject_id == "user-uuid-1"
    assert env.source_key == "issue:issue-uuid-1"
    assert env.metadata["identifier"] == "ENG-42"
    assert env.metadata["state"] == "In Progress"
    assert env.metadata["team"] == "ENG"
    assert env.metadata["assignee_email"] == "dev@acme.com"


def test_linear_issue_falls_back_to_creator():
    env = map_linear_record(
        "issues",
        {"id": "x", "createdAt": "2026-06-01T10:00:00Z", "creator": {"id": "c1"}},
    )
    assert env.subject_id == "c1"


def test_linear_unmapped_stream_is_skipped():
    assert map_linear_record("comments", {"id": "1"}) is None
    assert map_linear_record("issues", {"identifier": "no-id"}) is None
