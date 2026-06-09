"""Read schemas for the analytics metrics endpoints.

These serve dbt-built marts (the `analytics` schema, see transformation/dbt).
Granularity values match the frontend's `Granularity` type so query params map
one-to-one onto the chart filters.
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
