"""File-pipeline vs store-backed resolve parity checks."""

from __future__ import annotations

from dataclasses import dataclass

from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.ir.hashutil import plan_content_hash
from propel_metrics.ir.types import CompiledPlan
from propel_metrics.resolve import resolve_metrics
from propel_metrics.resolve.org import resolve_org
from propel_metrics.store.protocol import DefinitionStore


@dataclass(frozen=True, slots=True)
class ParityMismatch:
    metric_id: str
    file_hash: str
    store_hash: str


def _with_version(plan: CompiledPlan, version: str) -> CompiledPlan:
    return CompiledPlan(
        metric_id=plan.metric_id,
        definition_version=version,
        kind=plan.kind,
        aggregations=plan.aggregations,
        expression=plan.expression,
        dimensions=plan.dimensions,
        grains=plan.grains,
        windows=plan.windows,
        zero_denominator=plan.zero_denominator,
    )


def file_pipeline_hashes() -> dict[str, str]:
    """Content hashes for active propel.* metrics via the file pipeline.

    Aligns ``definition_version`` to the semantic int version so hashes are
    comparable to store-backed org resolve (which uses version ints).
    """
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    out: dict[str, str] = {}
    for mid, metric in by_id.items():
        if not mid.startswith("propel."):
            continue
        try:
            plan = build_compiled_plan(metric, by_id)
        except ValueError:
            continue
        plan = _with_version(plan, str(metric.version))
        out[mid] = plan_content_hash(plan)
    return out


def resolve_parity(
    store: DefinitionStore,
    org_id: str,
) -> list[ParityMismatch]:
    """Compare default (no param override) store resolve vs file pipeline.

    The org MetricSet must not override params for compared metrics; callers
    typically use an implicit/default_on set with empty params.
    """
    file_hashes = file_pipeline_hashes()
    result = resolve_org(store, org_id, persist_enrollment=False)
    mismatches: list[ParityMismatch] = []
    for metric in result.metrics:
        if not metric.metric_id.startswith("propel."):
            continue
        if metric.params:
            # Param overrides intentionally diverge from the file pipeline.
            continue
        expected = file_hashes.get(metric.metric_id)
        if expected is None:
            continue
        if metric.content_hash != expected:
            mismatches.append(
                ParityMismatch(
                    metric_id=metric.metric_id,
                    file_hash=expected,
                    store_hash=metric.content_hash,
                )
            )
    return mismatches
