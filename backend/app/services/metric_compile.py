"""Compile orchestration: dirty-set enqueue + single-flight runs."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status
from propel_metrics.codegen.shared import compile_org_results
from propel_metrics.paths import GENERATED_DIR
from propel_metrics.resolve.org import resolve_org
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import SYSTEM_ORG
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric_definition import MetricCompileDirty, MetricCompileRun
from app.models.tenant import Tenant
from app.services.metric_store import SqlAlchemyDefinitionStore

logger = logging.getLogger("propel.metric_compile")

CompileSource = Literal["files", "db"]


def compile_source() -> CompileSource:
    raw = os.environ.get("METRICS_COMPILE_SOURCE", "").strip().lower()
    if not raw:
        try:
            from app.config import get_settings

            raw = get_settings().metrics_compile_source.strip().lower()
        except Exception:
            raw = "files"
    return "db" if raw == "db" else "files"


async def _mark_dirty(
    session: AsyncSession, content_hashes: list[str], reason: str
) -> None:
    for h in content_hashes:
        if not h:
            continue
        existing = await session.get(MetricCompileDirty, h)
        if existing is None:
            session.add(MetricCompileDirty(content_hash=h, reason=reason))
        else:
            existing.reason = reason


async def enqueue_compile(
    session: AsyncSession,
    *,
    trigger: str,
    content_hashes: list[str] | None = None,
    reason: str = "enqueue",
) -> MetricCompileRun | None:
    """Mark hashes dirty and start a single-flight compile run if none running.

    Uses a nested transaction for the run insert so a conflict does not roll
    back the caller's outer unit of work (e.g. an activation).
    """
    if content_hashes:
        await _mark_dirty(session, content_hashes, reason)

    # Fast path: already running
    existing = (
        (
            await session.execute(
                select(MetricCompileRun).where(MetricCompileRun.status == "running")
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        await session.flush()
        logger.info("compile already running; dirtied %s", content_hashes)
        return None

    run = MetricCompileRun(
        id=uuid.uuid4(),
        status="running",
        trigger=trigger,
        report_json={"queued_hashes": list(content_hashes or [])},
    )
    try:
        async with session.begin_nested():
            session.add(run)
            await session.flush()
    except IntegrityError:
        logger.info("compile race lost; dirtied %s", content_hashes)
        return None

    return run


async def _hydrate_all_orgs(session: AsyncSession) -> MemoryDefinitionStore:
    sql = SqlAlchemyDefinitionStore(session)
    mem = MemoryDefinitionStore()
    system = await sql.list_definitions(SYSTEM_ORG)
    if not system:
        written = import_system_metrics(mem)
        for row in written:
            await sql.upsert_definition(row)
        await session.flush()
        system = await sql.list_definitions(SYSTEM_ORG)
    for row in system:
        mem.upsert_definition(row)

    result = await session.execute(select(Tenant).where(Tenant.deleted_at.is_(None)))
    for tenant in result.scalars().all():
        for row in await sql.list_definitions(tenant.slug):
            mem.upsert_definition(row)
    return mem


async def run_compile(
    session: AsyncSession,
    *,
    run_id: uuid.UUID | None = None,
    output_dir: Path | None = None,
    full: bool = False,
) -> dict[str, Any]:
    """Resolve all orgs and regenerate dirty (or all) shared models.

    No-op when ``METRICS_COMPILE_SOURCE=files`` (CI file pipeline owns SQL).
    """
    if compile_source() != "db":
        report = {
            "skipped": True,
            "reason": "METRICS_COMPILE_SOURCE!=db",
            "source": compile_source(),
        }
        if run_id is not None:
            run = await session.get(MetricCompileRun, run_id)
            if run is not None:
                run.status = "skipped"
                run.finished_at = datetime.now(UTC)
                run.report_json = report
        return report

    run: MetricCompileRun | None = None
    if run_id is not None:
        run = await session.get(MetricCompileRun, run_id)
    if run is None:
        run = await enqueue_compile(session, trigger="manual")
        if run is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="compile already running"
            )

    dirty_rows = (await session.execute(select(MetricCompileDirty))).scalars().all()
    dirty = {r.content_hash for r in dirty_rows}
    dirty_filter = None if full else (dirty or None)

    mem = await _hydrate_all_orgs(session)
    result = await session.execute(select(Tenant).where(Tenant.deleted_at.is_(None)))
    tenants = list(result.scalars().all())
    org_results = [
        resolve_org(mem, tenant.slug, persist_enrollment=True) for tenant in tenants
    ]

    sql = SqlAlchemyDefinitionStore(session)
    for tenant in tenants:
        await sql.replace_enrollments(tenant.slug, mem.list_enrollments(tenant.slug))

    out = output_dir or GENERATED_DIR
    written = compile_org_results(
        org_results, output_dir=out, dirty_hashes=dirty_filter
    )
    cleared = list(dirty) if dirty_filter is not None else list(dirty)
    if cleared:
        await sql.clear_dirty(cleared)

    report = {
        "skipped": False,
        "source": "db",
        "orgs": [t.slug for t in tenants],
        "dirty_count": len(dirty),
        "full": full,
        "models_written": [str(p) for p in written],
    }
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    run.report_json = report
    logger.info("metric compile finished: %s", report)
    return report
