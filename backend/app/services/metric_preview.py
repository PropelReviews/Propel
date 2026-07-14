"""In-memory metric preview for the authoring UI (M5.3).

Validates → resolves → preview codegen → optional warehouse execution
(read-only, statement_timeout). Falls back to dry-run SQL when relations
are missing.
"""

from __future__ import annotations

import copy
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from fastapi import HTTPException, status
from propel_metrics.codegen.preview import render_preview_sql
from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.resolve import ResolvedMetric, apply_extends, content_hash
from propel_metrics.resolve.lifecycle import validate_yaml_text
from propel_metrics.resolve.org import load_org_mappings
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


async def _pick_schema(
    session: AsyncSession, *, relation_names: set[str]
) -> str | None:
    """Choose a schema where required relations exist; None → dry-run."""
    canaries = relation_names or {"pull_request"}
    for schema in _RELATION_SCHEMAS:
        for name in canaries:
            if await _schema_has_relation(session, schema, name):
                return schema
    return None


def _jsonable_cell(value: Any) -> Any:
    """Coerce asyncpg/SQLAlchemy cell values to JSON-safe primitives."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, memoryview)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


async def _ic_identity_keys(
    session: AsyncSession, *, tenant_id: str, user_id: str
) -> set[str]:
    """Return external ids/logins for the user that may appear in person dims."""
    from uuid import UUID as _UUID

    from sqlalchemy import select

    from app.models.enums import IntegrationProvider
    from app.models.external_identity import ExternalIdentity

    try:
        uid = _UUID(user_id)
        tid = _UUID(tenant_id)
    except ValueError:
        return set()
    result = await session.execute(
        select(
            ExternalIdentity.external_user_id, ExternalIdentity.external_login
        ).where(
            ExternalIdentity.tenant_id == tid,
            ExternalIdentity.propel_user_id == uid,
            ExternalIdentity.provider == IntegrationProvider.github,
        )
    )
    keys: set[str] = set()
    for ext_id, login in result.all():
        if ext_id:
            keys.add(str(ext_id))
        if login:
            keys.add(str(login))
    return keys


def _apply_ic_row_filter(
    rows: list[dict[str, Any]],
    *,
    identity_keys: set[str],
    person_fields: list[str],
) -> list[dict[str, Any]]:
    """Keep only rows whose person-dim columns match the caller's identity."""
    if not identity_keys or not person_fields:
        return rows
    candidates = []
    for field in person_fields:
        candidates.extend([field, f"dim_{field}", field.replace(".", "_")])
    out: list[dict[str, Any]] = []
    for row in rows:
        matched = False
        saw_person_col = False
        for key, value in row.items():
            if key in candidates or any(key.endswith(f"_{f}") for f in person_fields):
                saw_person_col = True
                if value is not None and str(value) in identity_keys:
                    matched = True
                    break
        # Aggregate-shaped rows (no person column) pass through.
        if matched or not saw_person_col:
            out.append(row)
    return out


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

        try:
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

            mapped = load_org_mappings(mem, org_slug)
            # Index is by to_dimension name and mapping id; keep name keys only.
            mapped_by_name = {
                name: dim for name, dim in mapped.items() if name == dim.name
            }
            plan = build_compiled_plan(
                by_resolved[mid],
                by_resolved,
                mapped_dimensions=mapped_by_name or None,
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — surface as JSON 400 for the UI
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "PREVIEW_COMPILE_FAILED",
                    "message": str(exc),
                },
            ) from exc

        relation_names: set[str] = set()
        for agg in plan.aggregations.values():
            relation_names.add(agg.operand.dbt_model)
        if plan.windows:
            relation_names.add("dim_step_spine")

        schema = await _pick_schema(session, relation_names=relation_names)
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
                    fetched = [_jsonable_cell_row(dict(r)) for r in mapping.fetchall()]
                    rows = fetched
                    executed = True
                    if len(rows) >= int(preview["row_limit"]):
                        truncated = True

                    # IC visibility: do not leak other people's person-dim rows.
                    visibility = (flat.get("spec") or {}).get("visibility")
                    if visibility == "ic":
                        from propel_metrics.validate.loader import load_catalog

                        catalog = load_catalog()
                        entity = (flat.get("spec") or {}).get("entity")
                        fields = (catalog.get("entities") or {}).get(
                            entity or "", {}
                        ).get("fields") or {}
                        catalog_person = [
                            name
                            for name, meta in fields.items()
                            if isinstance(meta, dict) and meta.get("person")
                        ]
                        dims = list((flat.get("spec") or {}).get("dimensions") or [])
                        person_fields = [
                            d for d in dims if d in catalog_person
                        ] or catalog_person
                        keys = await _ic_identity_keys(
                            session, tenant_id=tenant_uuid, user_id=user_id
                        )
                        before = len(rows)
                        rows = _apply_ic_row_filter(
                            rows,
                            identity_keys=keys,
                            person_fields=person_fields,
                        )
                        if before and len(rows) < before:
                            diagnostics.append(
                                {
                                    "cte": "ic_visibility",
                                    "message": (
                                        "IC visibility: filtered to caller identity "
                                        f"({before} → {len(rows)} rows)."
                                    ),
                                }
                            )
                        elif not keys and person_fields:
                            diagnostics.append(
                                {
                                    "cte": "ic_visibility",
                                    "message": (
                                        "IC visibility: no linked external identity; "
                                        "showing aggregate-shaped rows only."
                                    ),
                                }
                            )

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


def _jsonable_cell_row(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _jsonable_cell(v) for k, v in row.items()}
