"""Read queries backing the ingestion observability endpoints.

All queries are tenant-scoped and read-only (no commits). Aggregates use a
single GROUP BY each so the Data page stays cheap to render.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datapoint import Datapoint
from app.models.ingestion_run import IngestionRun
from app.models.raw_record import RawRecord
from app.schemas.ingestion import CountByLabel, IngestionStats

_DEFAULT_RUN_LIMIT = 20


async def list_recent_runs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    limit: int = _DEFAULT_RUN_LIMIT,
) -> list[IngestionRun]:
    result = await session.execute(
        select(IngestionRun)
        .where(IngestionRun.tenant_id == tenant_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def datapoint_stats(
    session: AsyncSession, tenant_id: uuid.UUID
) -> IngestionStats:
    total_datapoints = await session.scalar(
        select(func.count())
        .select_from(Datapoint)
        .where(Datapoint.tenant_id == tenant_id)
    )
    total_raw_records = await session.scalar(
        select(func.count())
        .select_from(RawRecord)
        .where(RawRecord.tenant_id == tenant_id)
    )
    last_run_at = await session.scalar(
        select(func.max(IngestionRun.started_at)).where(
            IngestionRun.tenant_id == tenant_id
        )
    )

    by_kind = await _count_by(session, tenant_id, Datapoint.kind)
    by_source = await _count_by(session, tenant_id, Datapoint.source)

    return IngestionStats(
        total_datapoints=int(total_datapoints or 0),
        total_raw_records=int(total_raw_records or 0),
        by_kind=by_kind,
        by_source=by_source,
        last_run_at=last_run_at,
    )


async def _count_by(
    session: AsyncSession, tenant_id: uuid.UUID, column
) -> list[CountByLabel]:
    result = await session.execute(
        select(column, func.count())
        .where(Datapoint.tenant_id == tenant_id)
        .group_by(column)
        .order_by(func.count().desc())
    )
    return [
        CountByLabel(label=label, count=int(count)) for label, count in result.all()
    ]
