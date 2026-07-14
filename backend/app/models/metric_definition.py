"""ORM models for the M4 metric definition store."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"
    __table_args__ = (
        Index(
            "one_active_version",
            "org_id",
            "metric_id",
            unique=True,
            postgresql_where=text("status in ('active','broken')"),
        ),
        Index(
            "defs_by_hash",
            "content_hash",
            postgresql_where=text("status = 'active'"),
        ),
    )

    org_id: Mapped[str] = mapped_column(Text, primary_key=True)
    metric_id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    yaml: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    parent_pin: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    catalog_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrgMetricEnrollment(Base):
    __tablename__ = "org_metric_enrollment"

    org_id: Mapped[str] = mapped_column(Text, primary_key=True)
    metric_id: Mapped[str] = mapped_column(Text, primary_key=True)
    definition_org: Mapped[str] = mapped_column(Text, nullable=False)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    params_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class DefinitionNotice(Base):
    __tablename__ = "definition_notices"
    __table_args__ = (Index("ix_definition_notices_org_metric", "org_id", "metric_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[str] = mapped_column(Text, nullable=False)
    metric_id: Mapped[str] = mapped_column(Text, nullable=False)
    notice: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MetricCompileRun(Base):
    __tablename__ = "metric_compile_runs"
    __table_args__ = (
        Index(
            "one_running_compile",
            "status",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)


class MetricCompileDirty(Base):
    __tablename__ = "metric_compile_dirty"

    content_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
