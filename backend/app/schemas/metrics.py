"""Read schemas for the analytics metrics endpoints.

These serve dbt-built marts (the `analytics` schema, see transformation/dbt).
Granularity values match the frontend's `Granularity` type so query params map
one-to-one onto the chart filters.

DORA-aligned primitives currently exposed:
  - deployment frequency   → published GitHub Releases
  - pull-request activity  → throughput (opened / merged / closed)
  - cycle time             → lead-time-for-changes proxy (PR open → merge)
  - review latency         → lead-time breakdown / review flow
  - change failure         → change-fail-rate proxy (revert-titled merges)

Additional base primitives:
  - review comments        → GitHub PR review-comment throughput
  - workflow runs          → GitHub Actions run activity
  - tickets / comments / description edits / projects
    (normalized across trackers; source is a mart dimension)
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Granularity = Literal["daily", "weekly", "monthly"]

# `org` reads tenant-wide marts; `me` filters to the caller's linked GitHub
# identity (resolved server-side — clients never pass an author).
MetricScope = Literal["org", "me"]


class PullRequestActivityPoint(BaseModel):
    """PR activity bucketed to one period (day/week/month start)."""

    period_start: date
    opened: int
    merged: int
    closed: int


class PullRequestActivityResponse(BaseModel):
    granularity: Granularity
    points: list[PullRequestActivityPoint]


class DeploymentFrequencyPoint(BaseModel):
    """GitHub Release deployment counts bucketed to one period."""

    period_start: date
    releases_published: int
    production_releases: int


class DeploymentFrequencyResponse(BaseModel):
    granularity: Granularity
    points: list[DeploymentFrequencyPoint]


class CycleTimePoint(BaseModel):
    """PR cycle-time (lead-time proxy) bucketed to one period."""

    period_start: date
    prs_merged: int
    median_hours: float
    avg_hours: float
    p90_hours: float


class CycleTimeResponse(BaseModel):
    granularity: Granularity
    points: list[CycleTimePoint]


class ReviewLatencyPoint(BaseModel):
    """Review-latency primitives bucketed to one period."""

    period_start: date
    prs_first_reviewed: int
    median_hours_to_first_review: float | None
    reviews_submitted: int


class ReviewLatencyResponse(BaseModel):
    granularity: Granularity
    points: list[ReviewLatencyPoint]


class ChangeFailurePoint(BaseModel):
    """Change-failure proxy (revert rate) bucketed to one period."""

    period_start: date
    prs_merged: int
    prs_reverted: int
    change_failure_rate: float


class ChangeFailureResponse(BaseModel):
    granularity: Granularity
    points: list[ChangeFailurePoint]


class ReviewCommentsPoint(BaseModel):
    """GitHub PR review-comment throughput bucketed to one period."""

    period_start: date
    review_comments_created: int


class ReviewCommentsResponse(BaseModel):
    granularity: Granularity
    points: list[ReviewCommentsPoint]


class WorkflowRunsPoint(BaseModel):
    """GitHub Actions workflow-run activity bucketed to one period."""

    period_start: date
    runs_started: int
    runs_completed: int
    runs_success: int
    runs_failure: int


class WorkflowRunsResponse(BaseModel):
    granularity: Granularity
    points: list[WorkflowRunsPoint]


class TicketActivityPoint(BaseModel):
    """Ticket activity across issue trackers, bucketed to one period."""

    period_start: date
    tickets_created: int
    tickets_completed: int
    tickets_canceled: int


class TicketActivityResponse(BaseModel):
    granularity: Granularity
    points: list[TicketActivityPoint]


class TicketCommentsPoint(BaseModel):
    """Ticket-comment throughput across issue trackers, bucketed to one period."""

    period_start: date
    comments_created: int


class TicketCommentsResponse(BaseModel):
    granularity: Granularity
    points: list[TicketCommentsPoint]


class ProjectActivityPoint(BaseModel):
    """Project activity across project trackers, bucketed to one period."""

    period_start: date
    projects_created: int
    projects_completed: int
    projects_canceled: int


class ProjectActivityResponse(BaseModel):
    granularity: Granularity
    points: list[ProjectActivityPoint]


class TicketDescriptionEditsPoint(BaseModel):
    """Ticket description-edit counts across issue trackers."""

    period_start: date
    description_edits: int


class TicketDescriptionEditsResponse(BaseModel):
    granularity: Granularity
    points: list[TicketDescriptionEditsPoint]
