"""Thin field mapping: a tap-github-copilot record -> measurement envelope.

Copilot usage is a periodic per-user-day aggregate. GitHub restates the last
~2 days, so this is modeled as a measurement: one row per (subject, period),
upserted on observed_at (newest wins). Still landing, not analytics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from target_propel.envelopes.github import Envelope

COPILOT_STREAM = "copilot_usage"
_TOOL_COPILOT = "github_copilot"
_NAME = "copilot.usage"

# Fields that identify the row rather than describe usage; everything else is
# passed through to metadata as-is.
_IDENTITY_FIELDS = {"day", "date", "user_login", "user", "org", "team"}


def _parse_day(record: dict) -> datetime:
    raw = record.get("day") or record.get("date")
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(UTC)
    else:
        parsed = datetime.now(UTC)
    return parsed.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)


def map_copilot_record(record: dict) -> Envelope | None:
    period_start = _parse_day(record)
    period_end = period_start + timedelta(days=1)

    user = record.get("user_login") or record.get("user")
    if user:
        subject_type, subject_id = "user", str(user)
    else:
        subject_type = "org"
        subject_id = str(record.get("org") or "unknown")

    day_key = period_start.date().isoformat()
    metadata = {k: v for k, v in record.items() if k not in _IDENTITY_FIELDS}
    if record.get("org"):
        metadata["org"] = record["org"]

    return Envelope(
        kind="measurement",
        name=_NAME,
        tool=_TOOL_COPILOT,
        subject_type=subject_type,
        subject_id=subject_id,
        occurred_at=period_start,
        source_key=f"{subject_id}:{day_key}",
        source_id=f"{subject_id}:{day_key}",
        metadata=metadata,
        period_start=period_start,
        period_end=period_end,
    )
