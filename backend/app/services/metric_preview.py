"""In-memory metric preview for the authoring UI (M5.3).

Validates → resolves → preview codegen → optional warehouse execution
(read-only, statement_timeout). Falls back to dry-run SQL when relations
are missing.
"""

from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException, status
from propel_metrics.codegen.preview import render_preview_sql
from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.resolve import ResolvedMetric, apply_extends, content_hash
from propel_metrics.resolve.lifecycle import validate_yaml_text
from propel_metrics.resolve.params import bind_params
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metric_definitions import _hydrate, ensure_system_imported

_single_flight: dict[str, float] = {}

# Prefer analytics schema (dbt); fall back to public for local stubs.
_RELATION_SCHEMAS = ("analytics", "public")


async def _schema_has_relation(
    session: AsyncSession, schema: str, relation: str
) -> bool:
    result = await session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :name
            LIMIT 1
            """
        ),
        {"schema": schema, "name": relation},
    )
    return result.scalar() is not None


async def _pick_schema(session: AsyncSession, plan_sql: str) -> str | None:
    """Choose a schema where rewritten refs exist; None → dry-run."""
    # Collect relation names from rewritten SQL of form schema.name
    # We probe for pull_request / dim_step_spine as canaries.
    for schema in _RELATION_SCHEMAS:
        if await _schema_has_relation(session, schema, "pull_request"):
            return schema
        if "dim_step_spine" in plan_sql and await _schema_has_relation(
            session, schema, "dim_step_spine"
        ):
            return schema
    return None


async def preview_definition(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    tenant_uuid: str,
    user_id: str,
) -> dict[str, Any]:
    now = time.monotonic()
    stale = [k for k, t0 in _single_flight.items() if now - t0 > 30]
    for k in stale:
        _single_flight.pop(k, None)
    if user_id in _single_flight:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Preview already running for this user",
        )
    _single_flight[user_id] = now

    try:
        await ensure_system_imported(session)
        errors = validate_yaml_text(yaml_text)
        if errors:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "VALIDATION_FAILED", "errors": errors},
            )

        doc = yaml.safe_load(yaml_text)
        if not isinstance(doc, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid YAML")

        mem, _sql = await _hydrate(session, org_slug)
        by_docs: dict[str, dict[str, Any]] = {}
        for row in mem.list_active_system_metrics():
            by_docs[row.metric_id] = row.doc
        for row in mem.list_definitions(org_slug, kind="Metric", status="active"):
            by_docs.setdefault(row.metric_id, row.doc)

        mid = (doc.get("metadata") or {}).get("id")
        if not mid:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, detail="metadata.id required"
            )
        by_docs[mid] = doc

        flat = (
            apply_extends(doc, by_docs)
            if (doc.get("spec") or {}).get("extends")
            else doc
        )
        flat = copy.deepcopy(flat)
        flat["spec"] = bind_params(flat["spec"], None)

        by_resolved: dict[str, ResolvedMetric] = {}
        for rid, rdoc in by_docs.items():
            rflat = (
                apply_extends(rdoc, by_docs)
                if (rdoc.get("spec") or {}).get("extends")
                else rdoc
            )
            rspec = bind_params(copy.deepcopy(rflat["spec"]), None)
            meta = rflat.get("metadata") or {}
            by_resolved[rid] = ResolvedMetric(
                metric_id=rid,
                name=meta.get("name", rid),
                status=meta.get("status", "active"),
                version=int(meta.get("version", 1)),
                definition_version=content_hash(rspec),
                spec=rspec,
                source_path=Path(f"<preview:{rid}>"),
            )
        meta = flat.get("metadata") or {}
        by_resolved[mid] = ResolvedMetric(
            metric_id=mid,
            name=meta.get("name", mid),
            status=meta.get("status", "draft"),
            version=int(meta.get("version", 1)),
            definition_version=content_hash(flat["spec"]),
            spec=flat["spec"],
            source_path=Path(f"<preview:{mid}>"),
        )

        plan = build_compiled_plan(by_resolved[mid], by_resolved)
        schema = await _pick_schema(session, "")
        relation_schema = schema or "analytics"

        t0 = time.perf_counter()
        preview = render_preview_sql(
            plan,
            tenant_id=tenant_uuid,
            relation_schema=relation_schema,
        )
        timing_ms = int((time.perf_counter() - t0) * 1000)

        rows: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = []
        executed = False
        truncated = False

        if schema is None:
            diagnostics.append(
                {
                    "cte": "preview",
                    "message": (
                        "Dry-run preview: no analytics/public entity tables found. "
                        "SQL generated; warehouse execution skipped."
                    ),
                }
            )
        else:
            try:
                async with session.begin_nested():
                    await session.execute(text("SET LOCAL statement_timeout = '10s'"))
                    result = await session.execute(text(preview["sql"]))
                    mapping = result.mappings()
                    fetched = [dict(r) for r in mapping.fetchall()]
                    rows = fetched
                    executed = True
                    if len(rows) >= int(preview["row_limit"]):
                        truncated = True

                    diag_sql = preview.get("diagnostics_sql")
                    if diag_sql:
                        diag_result = await session.execute(text(diag_sql))
                        for r in diag_result.mappings().fetchall():
                            diagnostics.append(
                                {
                                    "cte": r["cte"],
                                    "rows_out": int(r["row_count"]),
                                }
                            )
                    if not rows:
                        if diagnostics:
                            ordered = sorted(
                                diagnostics,
                                key=lambda d: d.get("rows_out", 0),
                                reverse=True,
                            )
                            zero = next(
                                (
                                    d
                                    for d in diagnostics
                                    if int(d.get("rows_out", -1)) == 0
                                ),
                                None,
                            )
                            if zero:
                                before = next(
                                    (
                                        d
                                        for d in ordered
                                        if int(d.get("rows_out", 0)) > 0
                                    ),
                                    None,
                                )
                                msg = f"0 rows after CTE `{zero['cte']}`"
                                if before:
                                    msg += (
                                        f" ({before['rows_out']} before in "
                                        f"`{before['cte']}`)"
                                    )
                                diagnostics.insert(
                                    0, {"cte": zero["cte"], "message": msg}
                                )
                        else:
                            diagnostics.append(
                                {
                                    "cte": "preview",
                                    "message": (
                                        "Query returned 0 rows in the preview window."
                                    ),
                                }
                            )
            except Exception as exc:  # noqa: BLE001 — surface as diagnostic
                diagnostics.append(
                    {
                        "cte": "preview",
                        "message": (
                            f"Execution failed ({type(exc).__name__}: {exc}); "
                            "returning generated SQL only."
                        ),
                    }
                )
                executed = False
                rows = []

        timing_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "rows": rows,
            "timing_ms": timing_ms,
            "sql": preview["sql"],
            "grain": preview["grain"],
            "diagnostics": diagnostics,
            "truncated": truncated,
            "sampled": False,
            "executed": executed,
            "metric_id": mid,
        }
    finally:
        _single_flight.pop(user_id, None)
