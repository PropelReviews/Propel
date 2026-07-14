"""Pydantic schemas for metric definition management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MetricSummaryRead(BaseModel):
    """Enriched catalog row (M5)."""

    metric_id: str
    name: str
    version: int
    revision: int = 1
    status: str
    content_hash: str | None = None
    visibility: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    entity: str | None = None
    source: Literal["standard", "standard_customized", "custom", "variant"] = "custom"
    extends: str | None = None
    params_bound: dict[str, Any] | None = None
    draft_pending: bool = False
    notices: list[dict[str, Any]] = Field(default_factory=list)
    compile_error: str | None = None
    updated_at: datetime | None = None
    enrolled: bool = True


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
    created_by: str | None = None
    created_at: datetime | None = None


class MetricVersionRead(BaseModel):
    metric_id: str
    version: int
    revision: int
    status: str
    content_hash: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    org_id: str


class YamlBody(BaseModel):
    yaml: str


class DraftPutBody(BaseModel):
    yaml: str
    expected_version: int | None = None
    expected_revision: int | None = None


class ClassifyBody(BaseModel):
    yaml: str
    previous_version: int | None = None


class ClassifyResponse(BaseModel):
    kind: Literal["none", "non_semantic", "semantic"]
    next_version: int
    next_revision: int
    previous_version: int | None = None
    previous_revision: int | None = None


class ValidateResponse(BaseModel):
    ok: bool
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class ActivateBody(BaseModel):
    version: int | None = None


class DiffBody(BaseModel):
    metric_id: str
    from_version: int | None = None
    to_version: int | None = None
    from_yaml: str | None = None
    to_yaml: str | None = None


class DiffResponse(BaseModel):
    changes: list[dict[str, Any]]
    summary: list[str]
    from_resolved: dict[str, Any] | None = None
    to_resolved: dict[str, Any] | None = None


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


class MetricCatalogField(BaseModel):
    name: str
    type: str
    role: str
    values: list[str] | None = None
    nullable: bool | None = None
    cardinality_estimate: int | None = None
    person: bool = False
    virtual: bool = False
    mapping_id: str | None = None


class MetricCatalogEntity(BaseModel):
    name: str
    grain: str | None = None
    dbt_model: str | None = None
    fields: list[MetricCatalogField]


class VirtualDimension(BaseModel):
    mapping_id: str
    entity: str
    from_field: str
    to_dimension: str


class MetricCatalogResponse(BaseModel):
    catalog_version: int
    cardinality: dict[str, int] = Field(default_factory=dict)
    entities: list[MetricCatalogEntity]
    virtual_dimensions: list[VirtualDimension] = Field(default_factory=list)


class DimensionMappingSummary(BaseModel):
    mapping_id: str
    entity: str | None = None
    from_field: str | None = None
    to_dimension: str | None = None
    version: int
    status: str


class GeneratedSqlResponse(BaseModel):
    metric_id: str
    content_hash: str | None = None
    sql: str
    source: Literal["file", "db", "missing"] = "file"


class MetricHealthSummary(BaseModel):
    broken_count: int
    notice_count: int
    open_parent_version_notices: int
    recent_compile_runs: list[CompileRunRead] = Field(default_factory=list)
    broken_metrics: list[dict[str, Any]] = Field(default_factory=list)


class PreviewBody(BaseModel):
    yaml: str


class PreviewResponse(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    timing_ms: int
    sql: str
    grain: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False
    sampled: bool = False
    executed: bool = False
    metric_id: str | None = None
