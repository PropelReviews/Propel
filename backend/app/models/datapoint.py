import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Normalized, source-agnostic envelope (ingestion spec §4). The contract every
# downstream reader (dbt, later) consumes. Generic at ingest: provider-specific
# detail stays in raw_record.payload and a passthrough `metadata`; nothing is
# aggregated, joined, or scored here.
#
# Idempotency (spec §6) is enforced by two partial unique indexes:
#   - events:       (tenant_id, source, source_key)            where kind='event'
#   - measurements: (tenant_id, tool, name, subject_id, period_start)
#                                                               where kind='measurement'


class Datapoint(Base):
    __tablename__ = "datapoint"
    __table_args__ = (
        Index(
            "datapoint_event_uq",
            "tenant_id",
            "source",
            "source_key",
            unique=True,
            postgresql_where=text("kind = 'event'"),
        ),
        Index(
            "datapoint_measure_uq",
            "tenant_id",
            "tool",
            "name",
            "subject_id",
            "period_start",
            unique=True,
            postgresql_where=text("kind = 'measurement'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    tool: Mapped[str] = mapped_column(String(50), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    # `metadata` is reserved on the declarative Base, so the attribute is `meta`.
    meta: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
