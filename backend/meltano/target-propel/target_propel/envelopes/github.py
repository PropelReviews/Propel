"""Thin field mapping: a tap-github record -> Propel datapoint envelope.

This is the only place that knows GitHub's record shapes, and it does the
minimum: pick the envelope columns (who/when/what), a stable source_key for
idempotency, and a passthrough metadata subset. No aggregation, joins, or
derived metrics — those belong to the dbt layer, later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

# tap-github stream name -> datapoint `name`. Streams not listed are skipped
# (still landed as raw_record by the sink, just no datapoint emitted).
_EVENT_STREAM_NAMES: dict[str, str] = {
    "pull_requests": "pull_request",
    "commits": "commit",
    "issues": "issue",
    "issue_comments": "comment",
    "pull_request_review_comments": "comment",
    "reviews": "review",
    "releases": "release",
}

_TOOL_GITHUB = "github"


@dataclass
class Envelope:
    kind: str
    name: str
    tool: str
    subject_type: str
    subject_id: str
    occurred_at: datetime
    source_key: str
    source_id: str | None
    metadata: dict = field(default_factory=dict)
    period_start: datetime | None = None
    period_end: datetime | None = None


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _user_login(record: dict) -> str:
    user = record.get("user")
    if isinstance(user, dict) and user.get("login"):
        return str(user["login"])
    # commits carry author at the top level (may be null for unlinked commits)
    author = record.get("author")
    if isinstance(author, dict) and author.get("login"):
        return str(author["login"])
    return "unknown"


def _repo_full_name(record: dict) -> str | None:
    org = record.get("org")
    repo = record.get("repo")
    if org and repo:
        return f"{org}/{repo}"
    if isinstance(record.get("base"), dict):
        base_repo = record["base"].get("repo")
        if isinstance(base_repo, dict) and base_repo.get("full_name"):
            return str(base_repo["full_name"])
    return repo if isinstance(repo, str) else None


def _occurred_at(stream: str, record: dict) -> datetime | None:
    if stream == "commits":
        commit = record.get("commit")
        if isinstance(commit, dict):
            for actor in ("author", "committer"):
                section = commit.get(actor)
                if isinstance(section, dict):
                    parsed = _parse_dt(section.get("date"))
                    if parsed is not None:
                        return parsed
    if stream == "reviews":
        return _parse_dt(record.get("submitted_at"))
    if stream == "releases":
        # Prefer published_at (drafts may lack it); fall back to created_at.
        return _parse_dt(record.get("published_at")) or _parse_dt(
            record.get("created_at")
        )
    return _parse_dt(record.get("created_at"))


def _source_key(name: str, record: dict) -> str:
    node_id = record.get("node_id")
    if node_id:
        return str(node_id)
    natural = record.get("id") or record.get("sha")
    return f"{name}:{natural}"


def _metadata(stream: str, record: dict) -> dict:
    # A small, useful passthrough subset. The full payload is always in
    # raw_record; this is just enough for downstream staging to key on without
    # re-reading raw. Not computed, not scored.
    meta: dict = {"stream": stream}
    repo = _repo_full_name(record)
    if repo:
        meta["repo"] = repo
    for key in ("number", "state", "html_url", "updated_at", "merged_at", "sha"):
        if record.get(key) is not None:
            meta[key] = record[key]
    if stream == "reviews" and record.get("pull_request_number") is not None:
        meta["pull_request_number"] = record["pull_request_number"]
    if stream == "releases":
        for key in ("tag_name", "name", "draft", "prerelease", "published_at"):
            if record.get(key) is not None:
                meta[key] = record[key]
    return meta


def map_github_record(stream: str, record: dict) -> Envelope | None:
    """Map a tap-github record to an Envelope, or None if the stream is unmapped."""
    name = _EVENT_STREAM_NAMES.get(stream)
    if name is None:
        return None

    occurred = _occurred_at(stream, record) or datetime.now(UTC)
    natural_id = record.get("id") or record.get("sha") or record.get("node_id")
    return Envelope(
        kind="event",
        name=name,
        tool=_TOOL_GITHUB,
        subject_type="user",
        subject_id=_user_login(record),
        occurred_at=occurred,
        source_key=_source_key(name, record),
        source_id=str(natural_id) if natural_id is not None else None,
        metadata=_metadata(stream, record),
    )
