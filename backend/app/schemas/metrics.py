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
  - Linear issues/comments/projects/description edits
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Granularity = Literal["daily", "weekly", "monthly"]


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


class LinearIssueActivityPoint(BaseModel):
    """Linear issue activity bucketed to one period."""

    period_start: date
    issues_created: int
    issues_completed: int
    issues_canceled: int


class LinearIssueActivityResponse(BaseModel):
    granularity: Granularity
    points: list[LinearIssueActivityPoint]


class LinearCommentsPoint(BaseModel):
    """Linear comment throughput bucketed to one period."""

    period_start: date
    comments_created: int


class LinearCommentsResponse(BaseModel):
    granularity: Granularity
    points: list[LinearCommentsPoint]


class LinearProjectsPoint(BaseModel):
    """Linear project activity bucketed to one period."""

    period_start: date
    projects_created: int
    projects_completed: int
    projects_canceled: int


class LinearProjectsResponse(BaseModel):
    granularity: Granularity
    points: list[LinearProjectsPoint]


class LinearDescriptionEditsPoint(BaseModel):
    """Linear issue description-edit counts bucketed to one period."""

    period_start: date
    description_edits: int


class LinearDescriptionEditsResponse(BaseModel):
    granularity: Granularity
    points: list[LinearDescriptionEditsPoint]
