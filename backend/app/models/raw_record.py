import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Append-only raw landing (ingestion spec §4). The immutable provider payload as
# fetched — audit, replay, and the lineage target for every datapoint. Dedup and
# restatement are resolved at the datapoint layer, never here.


class RawRecord(Base):
    __tablename__ = "raw_record"
    __table_args__ = (
        Index(
            "ix_raw_record_tenant_source_resource_fetched",
            "tenant_id",
            "source",
            "resource_type",
            "fetched_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
