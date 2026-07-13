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
