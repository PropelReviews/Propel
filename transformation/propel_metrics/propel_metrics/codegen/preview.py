"""Preview-mode SQL wrapping for authoring (M5.3).

Takes a CompiledPlan, keeps the coarsest grain, strips dbt Jinja for a
read-only executable statement with hard limits.
"""

from __future__ import annotations

import re
from typing import Any

from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.ir.types import CompiledPlan

_GRAIN_RANK = {"day": 0, "week": 1, "month": 2, "quarter": 3}


def coarsest_grain(grains: tuple[str, ...] | list[str]) -> str | None:
    if not grains:
        return None
    return max(grains, key=lambda g: _GRAIN_RANK.get(g, -1))


def plan_for_preview(plan: CompiledPlan) -> CompiledPlan:
    """Force a single coarsest calendar grain; drop windows for preview cost."""
    grain = coarsest_grain(plan.grains)
    grains = (grain,) if grain else ()
    return CompiledPlan(
        metric_id=plan.metric_id,
        definition_version=plan.definition_version,
        kind=plan.kind,
        aggregations=plan.aggregations,
        expression=plan.expression,
        dimensions=plan.dimensions,
        grains=grains,
        windows=(),
        zero_denominator=plan.zero_denominator,
    )


def _strip_dbt_jinja(sql: str, *, tenant_id: str | None) -> str:
    """Replace common Jinja tenant filter with a literal UUID predicate."""
    out = re.sub(r"\{\{\s*config\([^}]+\)\s*\}\}", "", sql)
    if tenant_id:
        tenant_clause = f"(base.tenant_id = '{tenant_id}'::uuid)"
    else:
        tenant_clause = "true"
    # Match the _TENANT_CLAUSE expansion pattern in generated SQL
    out = re.sub(
        r"\{%\s*if var\('tenant_id',\s*none\)\s*%\}.*?\{%\s*else\s*%\}.*?\{%\s*endif\s*%\}",
        tenant_clause,
        out,
        flags=re.DOTALL,
    )
    # Fallback if still present
    out = out.replace("{{ var(\"tenant_id\") }}", tenant_id or "")
    return out


def render_preview_sql(
    plan: CompiledPlan,
    *,
    tenant_id: str | None,
    row_limit: int = 500,
    days: int = 90,
) -> dict[str, Any]:
    """Return preview SQL + metadata (no warehouse execution)."""
    preview_plan = plan_for_preview(plan)
    raw = render_plan_sql(preview_plan, source="preview")
    executable = _strip_dbt_jinja(raw, tenant_id=tenant_id)
    # Wrap final select with time clamp + limit when possible
    wrapped = (
        "-- PREVIEW (read-only, last "
        f"{days} days, limit {row_limit})\n"
        "SET LOCAL statement_timeout = '10s';\n"
        f"WITH preview_src AS (\n{executable}\n)\n"
        "SELECT * FROM preview_src\n"
        f"WHERE bucket_start >= (current_date - interval '{days} days')\n"
        f"LIMIT {row_limit}\n"
    )
    return {
        "sql": wrapped,
        "grain": preview_plan.grains[0] if preview_plan.grains else None,
        "row_limit": row_limit,
        "days": days,
        "metric_id": plan.metric_id,
    }
