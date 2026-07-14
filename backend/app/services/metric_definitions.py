"""Metric definition management service (M4).

Loads org + system rows into an in-memory DefinitionStore, runs pure
propel_metrics lifecycle/resolve, then persists back through SQLAlchemy.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from propel_metrics.resolve.lifecycle import (
    DraftConflictError,
    activate,
    archive,
    classify_yaml_change,
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


def _source_badge(
    metric_id: str,
    *,
    extends: str | None,
    params_bound: dict[str, Any] | None,
) -> str:
    if extends:
        return "variant"
    if metric_id.startswith("propel."):
        if params_bound:
            return "standard_customized"
        return "standard"
    return "custom"


def _measure_type(doc: dict[str, Any] | None) -> str | None:
    if not doc:
        return None
    measure = (doc.get("spec") or {}).get("measure") or {}
    return measure.get("type")


async def list_resolved_summaries(
    session: AsyncSession,
    org_slug: str,
    *,
    referencable: bool = False,
    entity: str | None = None,
    include_drafts: bool = True,
    include_broken: bool = True,
) -> list[dict[str, Any]]:
    """Return enriched catalog rows for the authoring UI (M5)."""
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    result = resolve_org(mem, org_slug, persist_enrollment=True)
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    await session.commit()

    metric_set = await get_metric_set(session, org_slug)
    params_root = ((metric_set.get("doc") or {}).get("spec") or {}).get(
        "standard", {}
    ).get("params") or {}

    notices_by_metric: dict[str, list[dict[str, Any]]] = {}
    for n in await sql.list_notices(org_slug):
        notices_by_metric.setdefault(n.metric_id, []).append(
            {"id": n.id, "notice": n.notice, "payload": n.payload}
        )

    # Draft / broken rows owned by the org (not only enrolled actives)
    org_defs = await sql.list_definitions(org_slug, kind="Metric")
    drafts: dict[str, StoredDefinition] = {}
    broken: dict[str, StoredDefinition] = {}
    for row in org_defs:
        if row.status == "draft":
            prev = drafts.get(row.metric_id)
            if prev is None or row.version > prev.version:
                drafts[row.metric_id] = row
        elif row.status == "broken":
            broken[row.metric_id] = row

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in result.metrics:
        meta = m.source_doc.get("metadata") or {}
        spec = m.source_doc.get("spec") or {}
        mid = m.metric_id
        extends = spec.get("extends")
        bound = params_root.get(mid) if isinstance(params_root, dict) else None
        if not isinstance(bound, dict):
            bound = None
        mtype = _measure_type(m.source_doc)
        ent = spec.get("entity")
        if referencable:
            if mtype in {"ratio", "formula"}:
                continue
            if entity and ent and ent != entity:
                continue
        draft = drafts.get(mid)
        compile_error = None
        status = "active"
        if mid in broken:
            status = "broken"
            compile_error = (broken[mid].resolved_json or {}).get("compile_error")
            if isinstance(compile_error, dict):
                compile_error = compile_error.get("message") or str(compile_error)
        out.append(
            {
                "metric_id": mid,
                "name": meta.get("name", mid),
                "description": meta.get("description"),
                "tags": list(meta.get("tags") or []),
                "version": int(getattr(m, "definition_version", 1) or 1),
                "revision": 1,
                "status": status,
                "content_hash": m.content_hash,
                "visibility": spec.get("visibility"),
                "entity": ent,
                "source": _source_badge(mid, extends=extends, params_bound=bound),
                "extends": extends,
                "params_bound": bound,
                "draft_pending": draft is not None,
                "notices": notices_by_metric.get(mid, []),
                "compile_error": compile_error,
                "enrolled": True,
            }
        )
        seen.add(mid)

    if include_drafts:
        for mid, row in drafts.items():
            if mid in seen and not referencable:
                # already marked draft_pending on enrolled row
                continue
            if mid in seen:
                continue
            meta = (row.doc or {}).get("metadata") or {}
            spec = (row.doc or {}).get("spec") or {}
            extends = spec.get("extends")
            ent = spec.get("entity")
            if referencable:
                continue  # drafts are not referencable operands
            bound = params_root.get(mid) if isinstance(params_root, dict) else None
            if not isinstance(bound, dict):
                bound = None
            out.append(
                {
                    "metric_id": mid,
                    "name": meta.get("name", mid),
                    "description": meta.get("description"),
                    "tags": list(meta.get("tags") or []),
                    "version": row.version,
                    "revision": row.revision,
                    "status": "draft",
                    "content_hash": row.content_hash,
                    "visibility": spec.get("visibility"),
                    "entity": ent,
                    "source": _source_badge(mid, extends=extends, params_bound=bound),
                    "extends": extends,
                    "params_bound": bound,
                    "draft_pending": False,
                    "notices": notices_by_metric.get(mid, []),
                    "compile_error": None,
                    "enrolled": False,
                }
            )
            seen.add(mid)

    if include_broken:
        for mid, row in broken.items():
            if mid in seen:
                continue
            if referencable:
                continue
            meta = (row.doc or {}).get("metadata") or {}
            spec = (row.doc or {}).get("spec") or {}
            extends = spec.get("extends")
            err = (row.resolved_json or {}).get("compile_error")
            if isinstance(err, dict):
                err = err.get("message") or str(err)
            out.append(
                {
                    "metric_id": mid,
                    "name": meta.get("name", mid),
                    "description": meta.get("description"),
                    "tags": list(meta.get("tags") or []),
                    "version": row.version,
                    "revision": row.revision,
                    "status": "broken",
                    "content_hash": row.content_hash,
                    "visibility": spec.get("visibility"),
                    "entity": spec.get("entity"),
                    "source": _source_badge(mid, extends=extends, params_bound=None),
                    "extends": extends,
                    "params_bound": None,
                    "draft_pending": mid in drafts,
                    "notices": notices_by_metric.get(mid, []),
                    "compile_error": err if isinstance(err, str) else None,
                    "enrolled": False,
                }
            )

    # Fix version integers from enrollment when available
    enrollments = {e.metric_id: e for e in await sql.list_enrollments(org_slug)}
    for item in out:
        enr = enrollments.get(item["metric_id"])
        if enr is not None and item["status"] in {"active", "broken"}:
            item["version"] = enr.definition_version
            # Prefer store row revision
            store_org = (
                SYSTEM_ORG if item["metric_id"].startswith("propel.") else org_slug
            )
            stored = await sql.get_definition(
                store_org,
                item["metric_id"],
                version=enr.definition_version,
            )
            if stored is None and item["metric_id"].startswith("propel."):
                stored = await sql.get_definition(
                    org_slug, item["metric_id"], version=enr.definition_version
                )
            if stored is not None:
                item["revision"] = stored.revision

    out.sort(key=lambda r: r["metric_id"])
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
    orm = await _orm_definition(session, row.org_id, row.metric_id, version=row.version)
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
        "created_by": row.created_by,
        "created_at": orm.created_at if orm is not None else None,
        "notices": [
            {
                "id": n.id,
                "notice": n.notice,
                "payload": n.payload,
            }
            for n in notices
        ],
    }


async def _orm_definition(
    session: AsyncSession,
    org_id: str,
    metric_id: str,
    *,
    version: int | None = None,
):
    from sqlalchemy import select

    from app.models.metric_definition import MetricDefinition

    stmt = select(MetricDefinition).where(
        MetricDefinition.org_id == org_id,
        MetricDefinition.metric_id == metric_id,
    )
    if version is not None:
        stmt = stmt.where(MetricDefinition.version == version)
    else:
        stmt = stmt.order_by(MetricDefinition.version.desc())
    result = await session.execute(stmt)
    return result.scalars().first()


async def validate_definition(yaml_text: str) -> dict[str, Any]:
    errors = validate_yaml_text(yaml_text)
    return {"ok": not errors, "errors": errors, "warnings": []}


async def create_draft(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    created_by: str,
    expected_version: int | None = None,
    expected_revision: int | None = None,
) -> StoredDefinition:
    await ensure_system_imported(session)
    mem, sql = await _hydrate(session, org_slug)
    try:
        row = save_draft(
            mem,
            org_id=org_slug,
            yaml_text=yaml_text,
            created_by=created_by,
            expected_version=expected_version,
            expected_revision=expected_revision,
        )
    except DraftConflictError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "DRAFT_CONFLICT",
                "message": str(exc),
                "current_version": exc.current.version,
                "current_revision": exc.current.revision,
                "updated_by": exc.current.created_by,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await _persist(sql, mem, [org_slug, SYSTEM_ORG])
    await session.commit()
    return row


async def classify_definition(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    previous_version: int | None = None,
) -> dict[str, Any]:
    await ensure_system_imported(session)
    mem, _sql = await _hydrate(session, org_slug)
    try:
        return classify_yaml_change(
            mem,
            org_id=org_slug,
            yaml_text=yaml_text,
            previous_version=previous_version,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


async def get_metric_catalog(session: AsyncSession, org_slug: str) -> dict[str, Any]:
    """Entity catalog + org virtual dimensions for the builder (M5)."""
    from propel_metrics.validate.loader import load_catalog

    await ensure_system_imported(session)
    catalog = load_catalog()
    sql = SqlAlchemyDefinitionStore(session)
    mappings = await sql.list_definitions(
        org_slug, kind="DimensionMapping", status="active"
    )

    entities: list[dict[str, Any]] = []
    for name, ent in (catalog.get("entities") or {}).items():
        fields: list[dict[str, Any]] = []
        for fname, fmeta in (ent.get("fields") or {}).items():
            fields.append(
                {
                    "name": fname,
                    "type": fmeta.get("type"),
                    "role": fmeta.get("role"),
                    "values": fmeta.get("values"),
                    "nullable": fmeta.get("nullable"),
                    "cardinality_estimate": fmeta.get("cardinality_estimate"),
                    "person": bool(fmeta.get("person", False)),
                    "virtual": False,
                    "mapping_id": None,
                }
            )
        # Attach virtual dims for this entity from mappings
        for mrow in mappings:
            mspec = (mrow.doc or {}).get("spec") or {}
            if mspec.get("entity") != name:
                continue
            to_dim = mspec.get("to_dimension")
            if not to_dim:
                continue
            fields.append(
                {
                    "name": to_dim,
                    "type": "string",
                    "role": "dimension",
                    "values": None,
                    "nullable": True,
                    "cardinality_estimate": None,
                    "person": False,
                    "virtual": True,
                    "mapping_id": mrow.metric_id,
                }
            )
        entities.append(
            {
                "name": name,
                "grain": ent.get("grain"),
                "dbt_model": ent.get("dbt_model"),
                "fields": fields,
            }
        )

    virtual_dimensions = [
        {
            "mapping_id": m.metric_id,
            "entity": ((m.doc or {}).get("spec") or {}).get("entity"),
            "from_field": ((m.doc or {}).get("spec") or {}).get("from_field"),
            "to_dimension": ((m.doc or {}).get("spec") or {}).get("to_dimension"),
        }
        for m in mappings
    ]

    card = catalog.get("cardinality") or {}
    return {
        "catalog_version": int(catalog.get("catalogVersion") or 1),
        "cardinality": {
            k: int(v) for k, v in card.items() if isinstance(v, (int, float))
        },
        "entities": entities,
        "virtual_dimensions": virtual_dimensions,
    }


async def list_definition_versions(
    session: AsyncSession, org_slug: str, metric_id: str
) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.models.metric_definition import MetricDefinition

    await ensure_system_imported(session)
    orgs = [org_slug]
    if metric_id.startswith("propel."):
        orgs.append(SYSTEM_ORG)

    result = await session.execute(
        select(MetricDefinition)
        .where(
            MetricDefinition.metric_id == metric_id,
            MetricDefinition.org_id.in_(orgs),
            MetricDefinition.kind == "Metric",
        )
        .order_by(MetricDefinition.version.desc())
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return [
        {
            "metric_id": r.metric_id,
            "version": r.version,
            "revision": r.revision,
            "status": r.status,
            "content_hash": r.content_hash,
            "created_by": r.created_by,
            "created_at": r.created_at,
            "org_id": r.org_id,
        }
        for r in rows
    ]


async def list_dimension_mappings(
    session: AsyncSession, org_slug: str
) -> list[dict[str, Any]]:
    sql = SqlAlchemyDefinitionStore(session)
    # Prefer active; include latest draft if no active
    active = await sql.list_definitions(
        org_slug, kind="DimensionMapping", status="active"
    )
    by_id: dict[str, StoredDefinition] = {r.metric_id: r for r in active}
    for row in await sql.list_definitions(org_slug, kind="DimensionMapping"):
        by_id.setdefault(row.metric_id, row)
    out: list[dict[str, Any]] = []
    for mid, row in sorted(by_id.items()):
        spec = (row.doc or {}).get("spec") or {}
        out.append(
            {
                "mapping_id": mid,
                "entity": spec.get("entity"),
                "from_field": spec.get("from_field"),
                "to_dimension": spec.get("to_dimension"),
                "version": row.version,
                "status": row.status,
            }
        )
    return out


async def diff_definitions(
    session: AsyncSession,
    org_slug: str,
    *,
    metric_id: str,
    from_version: int | None = None,
    to_version: int | None = None,
    from_yaml: str | None = None,
    to_yaml: str | None = None,
) -> dict[str, Any]:
    import yaml
    from propel_metrics.resolve.structural_diff import (
        structural_diff,
        summarize_diff,
    )

    await ensure_system_imported(session)
    sql = SqlAlchemyDefinitionStore(session)

    async def _resolved(
        version: int | None, yaml_text: str | None
    ) -> dict[str, Any] | None:
        if yaml_text is not None:
            doc = yaml.safe_load(yaml_text)
            return doc if isinstance(doc, dict) else None
        if version is None:
            return None
        store_org = org_slug
        row = await sql.get_definition(org_slug, metric_id, version=version)
        if row is None and metric_id.startswith("propel."):
            row = await sql.get_definition(SYSTEM_ORG, metric_id, version=version)
            store_org = SYSTEM_ORG
        _ = store_org
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Version {version} not found for {metric_id}",
            )
        if row.resolved_json:
            return row.resolved_json
        return row.doc

    before = await _resolved(from_version, from_yaml)
    after = await _resolved(to_version, to_yaml)
    if after is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="to_version or to_yaml required"
        )
    changes = structural_diff(before or {}, after)
    return {
        "changes": changes,
        "summary": summarize_diff(changes),
        "from_resolved": before,
        "to_resolved": after,
    }


async def get_generated_sql(
    session: AsyncSession, org_slug: str, metric_id: str
) -> dict[str, Any]:
    from pathlib import Path

    from propel_metrics.codegen.shared import shared_model_filename
    from propel_metrics.codegen.sql import metric_model_filename
    from propel_metrics.paths import GENERATED_DIR

    await ensure_system_imported(session)
    sql_store = SqlAlchemyDefinitionStore(session)
    enrollments = await sql_store.list_enrollments(org_slug)
    enr = next((e for e in enrollments if e.metric_id == metric_id), None)
    content_hash = enr.content_hash if enr else None

    candidates: list[tuple[str, Path]] = []
    if content_hash:
        candidates.append(
            ("db", GENERATED_DIR / shared_model_filename(content_hash, metric_id))
        )
    candidates.append(("file", GENERATED_DIR / metric_model_filename(metric_id)))

    for source, path in candidates:
        if path.is_file():
            return {
                "metric_id": metric_id,
                "content_hash": content_hash,
                "sql": path.read_text(encoding="utf-8"),
                "source": source,
            }

    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail="Generated SQL not found (metric may not be compiled yet)",
    )


async def get_metric_health(session: AsyncSession, org_slug: str) -> dict[str, Any]:
    await ensure_system_imported(session)
    sql = SqlAlchemyDefinitionStore(session)
    broken_rows = [
        r for r in await sql.list_definitions(org_slug, kind="Metric", status="broken")
    ]
    # Also surface system metrics marked broken for this org? enrollment only.
    notices = await sql.list_notices(org_slug)
    open_parent = [n for n in notices if n.notice == "parent_version_available"]
    runs = await list_compile_runs(session)
    return {
        "broken_count": len(broken_rows),
        "notice_count": len(notices),
        "open_parent_version_notices": len(open_parent),
        "recent_compile_runs": runs[:10],
        "broken_metrics": [
            {
                "metric_id": r.metric_id,
                "version": r.version,
                "content_hash": r.content_hash,
            }
            for r in broken_rows
        ],
    }
