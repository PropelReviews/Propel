"""Pydantic schemas for metric definition management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricSummaryRead(BaseModel):
    metric_id: str
    name: str
    version: int
    status: str
    content_hash: str | None = None
    visibility: str | None = None


class MetricDefinitionRead(BaseModel):
    org_id: str
    metric_id: str
    version: int
    revision: int
    status: str
    kind: str
    yaml: str
    resolved_json: dict[str, Any] | None = None
    content_hash: str | None = None
    parent_pin: dict[str, Any] | None = None
    notices: list[dict[str, Any]] = Field(default_factory=list)


class YamlBody(BaseModel):
    yaml: str


class ValidateResponse(BaseModel):
    ok: bool
    errors: list[dict[str, Any]]


class ActivateBody(BaseModel):
    version: int | None = None


class MetricSetRead(BaseModel):
    org: str
    yaml: str | None
    doc: dict[str, Any]
    version: int | None
    status: str


class CompileRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    trigger: str
    report_json: dict[str, Any] | None = None
