"""Async SQLAlchemy adapter implementing propel_metrics DefinitionStore."""

from __future__ import annotations

import copy
import uuid

import yaml
from propel_metrics.store.protocol import (
    DefinitionNotice,
    EnrollmentRow,
    Kind,
    Status,
    StoredDefinition,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric_definition import (
    DefinitionNotice as NoticeModel,
)
from app.models.metric_definition import (
    MetricCompileDirty,
    MetricDefinition,
    OrgMetricEnrollment,
)


def _to_stored(row: MetricDefinition) -> StoredDefinition:
    doc = yaml.safe_load(row.yaml)
    if not isinstance(doc, dict):
        doc = {}
    return StoredDefinition(
        org_id=row.org_id,
        metric_id=row.metric_id,
        version=row.version,
        revision=row.revision,
        kind=row.kind,  # type: ignore[arg-type]
        yaml=row.yaml,
        doc=doc,
        resolved_json=row.resolved_json,
        content_hash=row.content_hash,
        status=row.status,  # type: ignore[arg-type]
        parent_pin=row.parent_pin,
        catalog_version=row.catalog_version,
        created_by=row.created_by,
    )


class SqlAlchemyDefinitionStore:
    """Session-scoped async store. Callers own commit/rollback."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_definition(
        self,
        org_id: str,
        metric_id: str,
        *,
        version: int | None = None,
        status: Status | None = None,
    ) -> StoredDefinition | None:
        stmt = select(MetricDefinition).where(
            MetricDefinition.org_id == org_id,
            MetricDefinition.metric_id == metric_id,
        )
        if version is not None:
            stmt = stmt.where(MetricDefinition.version == version)
        if status is not None:
            stmt = stmt.where(MetricDefinition.status == status)
        if version is None and status is None:
            stmt = stmt.where(MetricDefinition.status.in_(("active", "broken")))
            stmt = stmt.order_by(MetricDefinition.version.desc())
        elif version is None:
            stmt = stmt.order_by(MetricDefinition.version.desc())
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row is None and status is None and version is None:
            # fall back to latest any status
            result = await self.session.execute(
                select(MetricDefinition)
                .where(
                    MetricDefinition.org_id == org_id,
                    MetricDefinition.metric_id == metric_id,
                )
                .order_by(MetricDefinition.version.desc())
            )
            row = result.scalars().first()
        return _to_stored(row) if row else None

    async def list_definitions(
        self,
        org_id: str,
        *,
        kind: Kind | None = None,
        status: Status | None = None,
    ) -> list[StoredDefinition]:
        stmt = select(MetricDefinition).where(MetricDefinition.org_id == org_id)
        if kind is not None:
            stmt = stmt.where(MetricDefinition.kind == kind)
        if status is not None:
            stmt = stmt.where(MetricDefinition.status == status)
        stmt = stmt.order_by(MetricDefinition.metric_id, MetricDefinition.version)
        result = await self.session.execute(stmt)
        return [_to_stored(r) for r in result.scalars().all()]

    async def list_active_system_metrics(self) -> list[StoredDefinition]:
        return await self.list_definitions("__system", kind="Metric", status="active")

    async def upsert_definition(self, row: StoredDefinition) -> StoredDefinition:
        existing = await self.session.get(
            MetricDefinition, (row.org_id, row.metric_id, row.version)
        )
        if existing is None:
            existing = MetricDefinition(
                org_id=row.org_id,
                metric_id=row.metric_id,
                version=row.version,
            )
            self.session.add(existing)
        existing.revision = row.revision
        existing.kind = row.kind
        existing.yaml = row.yaml
        existing.resolved_json = row.resolved_json
        existing.content_hash = row.content_hash
        existing.status = row.status
        existing.parent_pin = row.parent_pin
        existing.catalog_version = row.catalog_version
        existing.created_by = row.created_by
        await self.session.flush()
        return copy.deepcopy(row)

    async def set_status(
        self,
        org_id: str,
        metric_id: str,
        version: int,
        status: Status,
    ) -> None:
        row = await self.session.get(MetricDefinition, (org_id, metric_id, version))
        if row is None:
            raise KeyError(f"missing {org_id}/{metric_id}@{version}")
        row.status = status
        await self.session.flush()

    async def replace_enrollments(self, org_id: str, rows: list[EnrollmentRow]) -> None:
        await self.session.execute(
            delete(OrgMetricEnrollment).where(OrgMetricEnrollment.org_id == org_id)
        )
        for r in rows:
            self.session.add(
                OrgMetricEnrollment(
                    org_id=r.org_id,
                    metric_id=r.metric_id,
                    definition_org=r.definition_org,
                    definition_version=r.definition_version,
                    params_json=r.params_json,
                    content_hash=r.content_hash,
                )
            )
        await self.session.flush()

    async def list_enrollments(self, org_id: str) -> list[EnrollmentRow]:
        result = await self.session.execute(
            select(OrgMetricEnrollment).where(OrgMetricEnrollment.org_id == org_id)
        )
        return [
            EnrollmentRow(
                org_id=r.org_id,
                metric_id=r.metric_id,
                definition_org=r.definition_org,
                definition_version=r.definition_version,
                params_json=r.params_json,
                content_hash=r.content_hash,
            )
            for r in result.scalars().all()
        ]

    async def add_notice(self, notice: DefinitionNotice) -> DefinitionNotice:
        model = NoticeModel(
            id=uuid.UUID(notice.id) if notice.id else uuid.uuid4(),
            org_id=notice.org_id,
            metric_id=notice.metric_id,
            notice=notice.notice,
            payload=notice.payload or {},
        )
        self.session.add(model)
        await self.session.flush()
        return DefinitionNotice(
            id=str(model.id),
            org_id=model.org_id,
            metric_id=model.metric_id,
            notice=model.notice,
            payload=model.payload,
        )

    async def list_notices(
        self, org_id: str, metric_id: str | None = None
    ) -> list[DefinitionNotice]:
        stmt = select(NoticeModel).where(NoticeModel.org_id == org_id)
        if metric_id is not None:
            stmt = stmt.where(NoticeModel.metric_id == metric_id)
        result = await self.session.execute(stmt)
        return [
            DefinitionNotice(
                id=str(n.id),
                org_id=n.org_id,
                metric_id=n.metric_id,
                notice=n.notice,
                payload=n.payload or {},
            )
            for n in result.scalars().all()
        ]

    async def mark_dirty(self, content_hash: str, reason: str) -> None:
        existing = await self.session.get(MetricCompileDirty, content_hash)
        if existing is None:
            self.session.add(
                MetricCompileDirty(content_hash=content_hash, reason=reason)
            )
        else:
            existing.reason = reason
        await self.session.flush()

    async def list_dirty(self) -> list[tuple[str, str]]:
        result = await self.session.execute(select(MetricCompileDirty))
        return [(r.content_hash, r.reason) for r in result.scalars().all()]

    async def clear_dirty(self, content_hashes: list[str]) -> None:
        if not content_hashes:
            return
        await self.session.execute(
            delete(MetricCompileDirty).where(
                MetricCompileDirty.content_hash.in_(content_hashes)
            )
        )
        await self.session.flush()
