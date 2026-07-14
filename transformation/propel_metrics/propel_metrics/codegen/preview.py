"""Preview-mode SQL wrapping for authoring (M5.3).

Takes a CompiledPlan, keeps the coarsest grain, strips dbt Jinja, rewrites
``ref('model')`` to schema-qualified relations, and adds time/row limits.
Optionally emits a companion diagnostics query (per-CTE ``count(*)``).
"""

from __future__ import annotations

import re
from typing import Any

from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.ir.types import CompiledPlan

_GRAIN_RANK = {"day": 0, "week": 1, "month": 2, "quarter": 3}
_REF_RE = re.compile(r"\{\{\s*ref\('([^']+)'\)\s*\}\}")
_CONFIG_RE = re.compile(r"\{\{\s*config\([^}]+\)\s*\}\}")
_TENANT_IF_RE = re.compile(
    r"\{%\s*if var\('tenant_id',\s*none\)\s*%\}.*?\{%\s*else\s*%\}.*?\{%\s*endif\s*%\}",
    re.DOTALL,
)


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


def rewrite_refs(sql: str, *, schema: str = "analytics") -> str:
    """Replace ``{{ ref('x') }}`` with ``schema.x`` (quoted if needed)."""

    def _sub(m: re.Match[str]) -> str:
        name = m.group(1)
        return f"{schema}.{name}"

    return _REF_RE.sub(_sub, sql)


def _strip_dbt_jinja(sql: str, *, tenant_id: str | None) -> str:
    """Remove config() and expand tenant_id Jinja to a literal predicate."""
    out = _CONFIG_RE.sub("", sql)
    tenant_clause = f"(base.tenant_id = '{tenant_id}'::uuid)" if tenant_id else "true"
    out = _TENANT_IF_RE.sub(tenant_clause, out)
    out = out.replace('{{ var("tenant_id") }}', tenant_id or "")
    return out


def _cte_names(sql: str) -> list[str]:
    """Best-effort extract of top-level CTE names from a WITH query."""
    # Match `name as (` at CTE boundaries (not perfect, good enough for diagnostics).
    return re.findall(r"(?:^|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s*\(", sql, re.M)


def _extract_with_body(executable: str) -> tuple[str, str]:
    """Split compiled SQL into (with_clause_body, final_select).

    ``render_plan_sql`` emits ``with <ctes>, final as (...) select * from final``.
    """
    text = executable.strip()
    # Drop leading SQL comments / blank lines
    lines = text.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("--")):
        lines.pop(0)
    text = "\n".join(lines).strip()
    if not text.lower().startswith("with"):
        return "", text
    # Find the final `select * from final` (or last select)
    m = re.search(r"\n\s*select\s+\*\s+from\s+final\s*$", text, re.I | re.M)
    if m:
        with_part = text[: m.start()].strip()
        # with_part is `with ... final as (...)` — drop leading `with`
        body = re.sub(r"^\s*with\s+", "", with_part, count=1, flags=re.I).rstrip(",")
        return body, "select * from final"
    return text[4:].strip(), "select * from final"


def render_preview_sql(
    plan: CompiledPlan,
    *,
    tenant_id: str | None,
    row_limit: int = 500,
    days: int = 90,
    relation_schema: str = "analytics",
) -> dict[str, Any]:
    """Return executable preview SQL + a diagnostics count query."""
    preview_plan = plan_for_preview(plan)
    raw = render_plan_sql(preview_plan, source="preview")
    stripped = _strip_dbt_jinja(raw, tenant_id=tenant_id)
    executable = rewrite_refs(stripped, schema=relation_schema)

    with_body, _final = _extract_with_body(executable)
    if not with_body:
        # Fallback: wrap whole statement (may fail if nested WITH)
        data_sql = (
            f"-- PREVIEW (last {days}d, limit {row_limit})\n"
            f"SELECT * FROM (\n{executable}\n) AS preview_src\n"
            f"WHERE bucket_start >= (current_date - interval '{days} days')\n"
            f"LIMIT {row_limit}\n"
        )
        diag_sql = None
        cte_names: list[str] = []
    else:
        grain = preview_plan.grains[0] if preview_plan.grains else "day"
        data_sql = (
            f"-- PREVIEW (last {days}d, limit {row_limit}, grain={grain})\n"
            f"WITH\n{with_body},\n"
            f"preview_src AS (\n"
            f"    SELECT * FROM final\n"
            f"    WHERE bucket_start >= (current_date - interval '{days} days')\n"
            f")\n"
            f"SELECT * FROM preview_src\n"
            f"LIMIT {row_limit}\n"
        )
        cte_names = _cte_names("with " + with_body)
        # Prefer known taps first
        preferred = [
            n
            for n in ("m_rows", "n_rows", "d_rows", f"grain_{grain}", "final")
            if n in cte_names
        ]
        taps = preferred or cte_names[:6]
        if taps:
            unions = "\nUNION ALL\n".join(
                (
                    f"SELECT '{name}'::text AS cte, "
                    f"count(*)::bigint AS row_count FROM {name}"
                )
                for name in taps
            )
            diag_sql = f"WITH\n{with_body}\n{unions}\n"
        else:
            diag_sql = None

    return {
        "sql": data_sql,
        "diagnostics_sql": diag_sql,
        "cte_names": cte_names,
        "grain": preview_plan.grains[0] if preview_plan.grains else None,
        "row_limit": row_limit,
        "days": days,
        "metric_id": plan.metric_id,
        "relation_schema": relation_schema,
    }
