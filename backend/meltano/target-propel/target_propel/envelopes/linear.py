"""Thin field mapping: a tap-linear record -> Propel datapoint envelope.

Linear issues are modeled as events (one per issue, keyed by the stable issue
id) — the same shape as GitHub issues. The subject is the assignee (who the
work is on), falling back to the creator. Landing keeps the full payload in
raw_record; this just picks the envelope columns and a small metadata subset.
No aggregation or joins — that belongs to the dbt layer, later.
"""

from __future__ import annotations

from datetime import UTC, datetime

from target_propel.envelopes.github import Envelope

ISSUES_STREAM = "issues"
_TOOL_LINEAR = "linear"
_NAME_ISSUE = "issue"


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


def _subject(record: dict) -> str:
    return (
        _person_id(record.get("assignee"))
        or _person_id(record.get("creator"))
        or "unknown"
    )


def _metadata(record: dict) -> dict:
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
    assignee = record.get("assignee")
    if isinstance(assignee, dict) and assignee.get("email"):
        meta["assignee_email"] = assignee["email"]
    return meta


def map_linear_record(stream: str, record: dict) -> Envelope | None:
    """Map a tap-linear record to an Envelope, or None if the stream is unmapped."""
    if stream != ISSUES_STREAM:
        return None

    issue_id = record.get("id")
    if not issue_id:
        return None

    occurred = _parse_dt(record.get("createdAt")) or datetime.now(UTC)
    return Envelope(
        kind="event",
        name=_NAME_ISSUE,
        tool=_TOOL_LINEAR,
        subject_type="user",
        subject_id=_subject(record),
        occurred_at=occurred,
        source_key=f"{_NAME_ISSUE}:{issue_id}",
        source_id=str(issue_id),
        metadata=_metadata(record),
    )
