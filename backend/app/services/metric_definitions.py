"""Metric definition management service (M4).

Loads org + system rows into an in-memory DefinitionStore, runs pure
propel_metrics lifecycle/resolve, then persists back through SQLAlchemy.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from propel_metrics.resolve.lifecycle import (
    activate,
    archive,
    repin,
    save_draft,
    validate_yaml_text,
)
from propel_metrics.resolve.org import resolve_org
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import (
    METRIC_SET_ID,
    SYSTEM_ORG,
    StoredDefinition,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metric_store import SqlAlchemyDefinitionStore


async def _hydrate(
    session: AsyncSession, org_id: str
) -> tuple[MemoryDefinitionStore, SqlAlchemyDefinitionStore]:
    sql = SqlAlchemyDefinitionStore(session)
    mem = MemoryDefinitionStore()
    for row in await sql.list_definitions(SYSTEM_ORG):
        mem.upsert_definition(row)
    if org_id != SYSTEM_ORG:
        for row in await sql.list_definitions(org_id):
            mem.upsert_definition(row)
    for n in await sql.list_notices(org_id):
        mem.add_notice(n)
    return mem, sql


async def _persist(
    sql: SqlAlchemyDefinitionStore,
    mem: MemoryDefinitionStore,
    org_ids: list[str],
) -> None:
    seen: set[tuple[str, str, int]] = set()
    for org in org_ids:
        for row in mem.list_definitions(org):
            key = (row.org_id, row.metric_id, row.version)
            if key in seen:
                continue
            seen.add(key)
            await sql.upsert_definition(row)
        await sql.replace_enrollments(org, mem.list_enrollments(org))
        for notice in mem.list_notices(org):
            # Only insert notices that look new (no id collision handling beyond add)
            existing = await sql.list_notices(org, notice.metric_id)
            if any(
                e.notice == notice.notice and e.payload == notice.payload
                for e in existing
            ):
                continue
            await sql.add_notice(notice)
    for content_hash, reason in mem.list_dirty():
        await sql.mark_dirty(content_hash, reason)


async def ensure_system_imported(session: AsyncSession) -> int:
    """Idempotent import of shipped propel.* YAMLs into ``__system``."""
    sql = SqlAlchemyDefinitionStore(session)
    existing = await sql.list_active_system_metrics()
    if existing:
        return len(existing)
    mem = MemoryDefinitionStore()
    written = import_system_metrics(mem)
    for row in written:
        await sql.upsert_definition(row)
    await session.commit()
    return len(written)


async def list_resolved_summaries(
    session: AsyncSession, org_slug: str
) -> list[dict[str, Any]]:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    result = resolve_org(mem, org_slug, persist_enrollment=True)
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    await session.commit()
    out: list[dict[str, Any]] = []
    for m in result.metrics:
        out.append(
            {
                "metric_id": m.metric_id,
                "version": m.definition_version,
                "status": "active",
                "content_hash": m.content_hash,
                "visibility": (m.source_doc.get("spec") or {}).get("visibility"),
                "name": (m.source_doc.get("metadata") or {}).get("name", m.metric_id),
            }
        )
    return out


async def get_definition_detail(
    session: AsyncSession, org_slug: str, metric_id: str
) -> dict[str, Any]:
    await ensure_system_imported(session)
    sql = SqlAlchemyDefinitionStore(session)
    # Prefer org-owned, else system
    row = await sql.get_definition(org_slug, metric_id)
    if row is None and metric_id.startswith("propel."):
        row = await sql.get_definition(SYSTEM_ORG, metric_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Metric not found")
    notices = await sql.list_notices(org_slug, metric_id)
    return {
        "org_id": row.org_id,
        "metric_id": row.metric_id,
        "version": row.version,
        "revision": row.revision,
        "status": row.status,
        "kind": row.kind,
        "yaml": row.yaml,
        "resolved_json": row.resolved_json,
        "content_hash": row.content_hash,
        "parent_pin": row.parent_pin,
        "notices": [
            {
                "id": n.id,
                "notice": n.notice,
                "payload": n.payload,
            }
            for n in notices
        ],
    }


async def validate_definition(yaml_text: str) -> dict[str, Any]:
    errors = validate_yaml_text(yaml_text)
    return {"ok": not errors, "errors": errors}


async def create_draft(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    created_by: str,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    try:
        row = save_draft(
            mem, org_id=org_slug, yaml_text=yaml_text, created_by=created_by
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    await session.commit()
    return row


async def activate_definition(
    session: AsyncSession,
    org_slug: str,
    metric_id: str,
    *,
    version: int | None = None,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    try:
        row = activate(
            mem,
            org_id=org_slug,
            metric_id=metric_id,
            version=version,
            known_orgs=[org_slug],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    from app.services import metric_compile as compile_svc

    await compile_svc.enqueue_compile(
        session,
        trigger="activate",
        content_hashes=[row.content_hash] if row.content_hash else [],
        reason=f"activate:{org_slug}/{metric_id}",
    )
    await session.commit()
    return row


async def repin_definition(
    session: AsyncSession,
    org_slug: str,
    metric_id: str,
    *,
    created_by: str,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    try:
        row = repin(
            mem,
            org_id=org_slug,
            metric_id=metric_id,
            activate_after=True,
            created_by=created_by,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    from app.services import metric_compile as compile_svc

    await compile_svc.enqueue_compile(
        session,
        trigger="repin",
        content_hashes=[row.content_hash] if row.content_hash else [],
        reason=f"repin:{org_slug}/{metric_id}",
    )
    await session.commit()
    return row


async def archive_definition(
    session: AsyncSession, org_slug: str, metric_id: str
) -> StoredDefinition:
    mem, sql = await _hydrate(session, org_slug)
    try:
        row = archive(mem, org_id=org_slug, metric_id=metric_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await _persist(sql, mem, [org_slug])
    await session.commit()
    return row


async def get_metric_set(session: AsyncSession, org_slug: str) -> dict[str, Any]:
    await ensure_system_imported(session)
    sql = SqlAlchemyDefinitionStore(session)
    row = await sql.get_definition(org_slug, METRIC_SET_ID, status="active")
    if row is None:
        return {
            "org": org_slug,
            "yaml": None,
            "doc": {
                "apiVersion": "propel/v1",
                "kind": "MetricSet",
                "metadata": {"org": org_slug},
                "spec": {"standard": {"mode": "default_on"}},
            },
            "version": None,
            "status": "implicit",
        }
    return {
        "org": org_slug,
        "yaml": row.yaml,
        "doc": row.doc,
        "version": row.version,
        "status": row.status,
    }


async def put_metric_set(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    created_by: str,
    activate_flag: bool = True,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    row = save_draft(mem, org_id=org_slug, yaml_text=yaml_text, created_by=created_by)
    if activate_flag:
        row = activate(
            mem,
            org_id=org_slug,
            metric_id=METRIC_SET_ID,
            version=row.version,
            known_orgs=[org_slug],
        )
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    from app.services import metric_compile as compile_svc

    enrollments = await sql.list_enrollments(org_slug)
    await compile_svc.enqueue_compile(
        session,
        trigger="metric_set",
        content_hashes=[e.content_hash for e in enrollments if e.content_hash],
        reason=f"metric_set:{org_slug}",
    )
    await session.commit()
    return row


async def put_dimension_mapping(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    created_by: str,
    activate_flag: bool = True,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    row = save_draft(mem, org_id=org_slug, yaml_text=yaml_text, created_by=created_by)
    if activate_flag:
        row = activate(
            mem,
            org_id=org_slug,
            metric_id=row.metric_id,
            version=row.version,
            known_orgs=[org_slug],
        )
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    from app.services import metric_compile as compile_svc

    enrollments = await sql.list_enrollments(org_slug)
    await compile_svc.enqueue_compile(
        session,
        trigger="dimension_mapping",
        content_hashes=[e.content_hash for e in enrollments if e.content_hash],
        reason=f"dimension_mapping:{org_slug}/{row.metric_id}",
    )
    await session.commit()
    return row


async def get_dimension_mapping(
    session: AsyncSession, org_slug: str, mapping_id: str
) -> dict[str, Any]:
    sql = SqlAlchemyDefinitionStore(session)
    row = await sql.get_definition(org_slug, mapping_id)
    if row is None or row.kind != "DimensionMapping":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    return {
        "metric_id": row.metric_id,
        "version": row.version,
        "status": row.status,
        "yaml": row.yaml,
        "doc": row.doc,
    }


async def list_compile_runs(session: AsyncSession) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.models.metric_definition import MetricCompileRun

    result = await session.execute(
        select(MetricCompileRun).order_by(MetricCompileRun.started_at.desc()).limit(50)
    )
    return [
        {
            "id": str(r.id),
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "status": r.status,
            "trigger": r.trigger,
            "report_json": r.report_json,
        }
        for r in result.scalars().all()
    ]
