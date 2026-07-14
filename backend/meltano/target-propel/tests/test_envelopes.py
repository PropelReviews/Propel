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
    assert map_github_record("unknown_stream", {"id": 1}) is None


def test_workflow_run_event():
    env = map_github_record(
        "workflow_runs",
        {
            "node_id": "WFR_1",
            "id": 99,
            "name": "CI",
            "status": "completed",
            "conclusion": "success",
            "event": "push",
            "run_number": 12,
            "created_at": "2026-06-01T09:00:00Z",
            "updated_at": "2026-06-01T09:05:00Z",
            "actor": {"login": "octocat"},
            "org": "acme",
            "repo": "web",
        },
    )
    assert env is not None
    assert env.kind == "event"
    assert env.name == "workflow_run"
    assert env.source_key == "WFR_1"
    assert env.subject_id == "octocat"
    assert env.occurred_at.isoformat().startswith("2026-06-01T09:05:00")
    assert env.metadata["conclusion"] == "success"
    assert env.metadata["repo"] == "acme/web"


def test_review_comment_event():
    env = map_github_record(
        "pull_request_review_comments",
        {
            "node_id": "PRRC_1",
            "id": 7,
            "created_at": "2026-06-01T11:00:00Z",
            "user": {"login": "reviewer"},
            "org": "acme",
            "repo": "web",
            "pull_request_number": 3,
            "path": "src/app.py",
        },
    )
    assert env is not None
    assert env.name == "review_comment"
    assert env.subject_id == "reviewer"
    assert env.metadata["pull_request_number"] == 3
    assert env.metadata["path"] == "src/app.py"


def test_release_event():
    env = map_github_record(
        "releases",
        {
            "node_id": "REL_1",
            "id": 42,
            "tag_name": "v1.2.0",
            "name": "1.2.0",
            "draft": False,
            "prerelease": False,
            "created_at": "2026-06-01T09:00:00Z",
            "published_at": "2026-06-01T10:00:00Z",
            "author": {"login": "octocat"},
            "org": "acme",
            "repo": "web",
        },
    )
    assert env is not None
    assert env.kind == "event"
    assert env.name == "release"
    assert env.source_key == "REL_1"
    assert env.subject_id == "octocat"
    assert env.occurred_at.isoformat().startswith("2026-06-01T10:00:00")
    assert env.metadata["tag_name"] == "v1.2.0"
    assert env.metadata["draft"] is False
    assert env.metadata["repo"] == "acme/web"


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
    assert map_linear_record("cycles", {"id": "1"}) is None
    assert map_linear_record("issues", {"identifier": "no-id"}) is None


def test_linear_comment_event():
    env = map_linear_record(
        "comments",
        {
            "id": "comment-1",
            "body": "Looks good",
            "createdAt": "2026-06-01T12:00:00Z",
            "issueId": "issue-uuid-1",
            "issue": {"id": "issue-uuid-1", "identifier": "ENG-42"},
            "user": {"id": "user-1", "email": "dev@acme.com"},
        },
    )
    assert env is not None
    assert env.name == "comment"
    assert env.tool == "linear"
    assert env.subject_id == "user-1"
    assert env.source_key == "comment:comment-1"
    assert env.metadata["issue_identifier"] == "ENG-42"


def test_linear_project_event():
    env = map_linear_record(
        "projects",
        {
            "id": "proj-1",
            "name": "Launch",
            "createdAt": "2026-06-01T08:00:00Z",
            "url": "https://linear.app/acme/project/launch",
            "status": {"name": "In Progress", "type": "started"},
            "lead": {"id": "lead-1"},
            "creator": {"id": "creator-1"},
        },
    )
    assert env is not None
    assert env.name == "project"
    assert env.subject_id == "lead-1"
    assert env.metadata["status"] == "In Progress"


def test_linear_description_edit_event():
    env = map_linear_record(
        "issue_description_edits",
        {
            "id": "hist-1",
            "createdAt": "2026-06-01T13:00:00Z",
            "updatedDescription": True,
            "issue": {
                "id": "issue-uuid-1",
                "identifier": "ENG-42",
                "url": "https://linear.app/acme/issue/ENG-42",
            },
            "actor": {"id": "editor-1"},
            "descriptionUpdatedBy": [{"id": "editor-1"}],
        },
    )
    assert env is not None
    assert env.name == "description_edit"
    assert env.subject_id == "editor-1"
    assert env.source_key == "description_edit:hist-1"
    assert env.metadata["issue_identifier"] == "ENG-42"
