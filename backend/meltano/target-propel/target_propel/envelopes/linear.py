"""Thin field mapping: a tap-linear record -> Propel datapoint envelope.

Linear primitives are modeled as events (one per entity, keyed by a stable id)
— the same shape as GitHub issues/comments. The subject is the person the work
is on or who authored the change. Landing keeps the full payload in raw_record;
this just picks the envelope columns and a small metadata subset. No
aggregation or joins — that belongs to the dbt layer.
"""

from __future__ import annotations

from datetime import UTC, datetime

from target_propel.envelopes.github import Envelope

ISSUES_STREAM = "issues"
COMMENTS_STREAM = "comments"
PROJECTS_STREAM = "projects"
DESCRIPTION_EDITS_STREAM = "issue_description_edits"

_TOOL_LINEAR = "linear"

_EVENT_STREAM_NAMES: dict[str, str] = {
    ISSUES_STREAM: "issue",
    COMMENTS_STREAM: "comment",
    PROJECTS_STREAM: "project",
    DESCRIPTION_EDITS_STREAM: "description_edit",
}


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _person_id(person: object) -> str | None:
    if not isinstance(person, dict):
        return None
    # Prefer a stable id; fall back to a human handle for readability.
    return (
        person.get("id")
        or person.get("email")
        or person.get("displayName")
        or person.get("name")
    )


def _first_person(*candidates: object) -> str:
    for candidate in candidates:
        if isinstance(candidate, list):
            for item in candidate:
                person_id = _person_id(item)
                if person_id:
                    return person_id
            continue
        person_id = _person_id(candidate)
        if person_id:
            return person_id
    return "unknown"


def _issue_metadata(record: dict) -> dict:
    meta: dict = {"stream": ISSUES_STREAM}
    for key in ("identifier", "title", "url", "priority", "estimate", "updatedAt"):
        if record.get(key) is not None:
            meta[key] = record[key]
    state = record.get("state")
    if isinstance(state, dict):
        if state.get("name"):
            meta["state"] = state["name"]
        if state.get("type"):
            meta["state_type"] = state["type"]
    team = record.get("team")
    if isinstance(team, dict) and team.get("key"):
        meta["team"] = team["key"]
    project = record.get("project")
    if isinstance(project, dict) and project.get("id"):
        meta["project_id"] = project["id"]
        if project.get("name"):
            meta["project_name"] = project["name"]
    assignee = record.get("assignee")
    if isinstance(assignee, dict) and assignee.get("email"):
        meta["assignee_email"] = assignee["email"]
    return meta


def _comment_metadata(record: dict) -> dict:
    meta: dict = {"stream": COMMENTS_STREAM}
    for key in ("url", "issueId", "projectId", "parentId", "updatedAt", "editedAt"):
        if record.get(key) is not None:
            meta[key] = record[key]
    issue = record.get("issue")
    if isinstance(issue, dict):
        if issue.get("id"):
            meta["issue_id"] = issue["id"]
        if issue.get("identifier"):
            meta["issue_identifier"] = issue["identifier"]
    project = record.get("project")
    if isinstance(project, dict) and project.get("id"):
        meta["project_id"] = project["id"]
        if project.get("name"):
            meta["project_name"] = project["name"]
    return meta


def _project_metadata(record: dict) -> dict:
    meta: dict = {"stream": PROJECTS_STREAM}
    for key in (
        "name",
        "url",
        "slugId",
        "priority",
        "progress",
        "health",
        "updatedAt",
        "targetDate",
        "startDate",
    ):
        if record.get(key) is not None:
            meta[key] = record[key]
    status = record.get("status")
    if isinstance(status, dict):
        if status.get("name"):
            meta["status"] = status["name"]
        if status.get("type"):
            meta["status_type"] = status["type"]
    return meta


def _description_edit_metadata(record: dict) -> dict:
    meta: dict = {"stream": DESCRIPTION_EDITS_STREAM}
    issue = record.get("issue")
    if isinstance(issue, dict):
        if issue.get("id"):
            meta["issue_id"] = issue["id"]
        if issue.get("identifier"):
            meta["issue_identifier"] = issue["identifier"]
        if issue.get("url"):
            meta["issue_url"] = issue["url"]
    return meta


def map_linear_record(stream: str, record: dict) -> Envelope | None:
    """Map a tap-linear record to an Envelope, or None if the stream is unmapped."""
    name = _EVENT_STREAM_NAMES.get(stream)
    if name is None:
        return None

    entity_id = record.get("id")
    if not entity_id:
        return None

    if stream == ISSUES_STREAM:
        subject = _first_person(record.get("assignee"), record.get("creator"))
        occurred = _parse_dt(record.get("createdAt")) or datetime.now(UTC)
        metadata = _issue_metadata(record)
    elif stream == COMMENTS_STREAM:
        subject = _first_person(record.get("user"), record.get("externalUser"))
        occurred = _parse_dt(record.get("createdAt")) or datetime.now(UTC)
        metadata = _comment_metadata(record)
    elif stream == PROJECTS_STREAM:
        subject = _first_person(record.get("lead"), record.get("creator"))
        occurred = _parse_dt(record.get("createdAt")) or datetime.now(UTC)
        metadata = _project_metadata(record)
    else:  # DESCRIPTION_EDITS_STREAM
        subject = _first_person(
            record.get("descriptionUpdatedBy"),
            record.get("actor"),
        )
        occurred = _parse_dt(record.get("createdAt")) or datetime.now(UTC)
        metadata = _description_edit_metadata(record)

    return Envelope(
        kind="event",
        name=name,
        tool=_TOOL_LINEAR,
        subject_type="user",
        subject_id=subject,
        occurred_at=occurred,
        source_key=f"{name}:{entity_id}",
        source_id=str(entity_id),
        metadata=metadata,
    )
