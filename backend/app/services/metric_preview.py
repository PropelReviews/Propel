"""In-memory metric preview for the authoring UI (M5.3).

Validates → resolves → preview codegen. Warehouse execution is best-effort:
when analytics tables are unavailable, return SQL + empty rows with a clear
diagnostic (dry-run mode).
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.metric_definitions import _hydrate, ensure_system_imported

_single_flight: dict[str, float] = {}


async def preview_definition(
    session: AsyncSession,
    org_slug: str,
    yaml_text: str,
    *,
    tenant_uuid: str,
    user_id: str,
) -> dict[str, Any]:
    now = time.monotonic()
    # Drop stale locks (>30s)
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
        # Ensure current doc wins
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
        t0 = time.perf_counter()
        preview = render_preview_sql(plan, tenant_id=tenant_uuid)
        timing_ms = int((time.perf_counter() - t0) * 1000)

        rows: list[dict[str, Any]] = []
        diagnostics = [
            {
                "cte": "preview",
                "message": (
                    "Dry-run preview: SQL generated. Warehouse execution is "
                    "skipped when analytics tables are unavailable in this environment."
                ),
            }
        ]
        executed = False
        try:
            from sqlalchemy import text

            # Attempt a lightweight read-only probe; ignore failures.
            async with session.begin_nested():
                await session.execute(text("SET LOCAL statement_timeout = '10s'"))
                # Don't actually run full preview SQL (dbt refs won't resolve here).
                executed = False
        except Exception:
            executed = False

        return {
            "rows": rows,
            "timing_ms": timing_ms,
            "sql": preview["sql"],
            "grain": preview["grain"],
            "diagnostics": diagnostics,
            "truncated": False,
            "sampled": False,
            "executed": executed,
            "metric_id": mid,
        }
    finally:
        _single_flight.pop(user_id, None)
