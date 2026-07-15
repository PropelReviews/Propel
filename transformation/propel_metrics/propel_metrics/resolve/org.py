"""Per-org resolution: MetricSet enrollment, params, pins, mappings → plans."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.ir.hashutil import plan_content_hash, plan_to_canonical_dict
from propel_metrics.ir.types import CompiledPlan, MappedDim
from propel_metrics.resolve import ResolvedMetric, apply_extends, content_hash
from propel_metrics.resolve.params import ParamBindError, bind_params
from propel_metrics.store.protocol import (
    METRIC_SET_ID,
    SYSTEM_ORG,
    DefinitionStore,
    EnrollmentRow,
    StoredDefinition,
)
from propel_metrics.validate.loader import load_catalog


@dataclass(frozen=True, slots=True)
class ResolvedOrgMetric:
    metric_id: str
    definition_org: str
    definition_version: int
    plan: CompiledPlan
    content_hash: str
    resolved_json: dict[str, Any]
    params: dict[str, Any] | None
    source_doc: dict[str, Any]


@dataclass(frozen=True, slots=True)
class OrgResolveResult:
    org_id: str
    metrics: tuple[ResolvedOrgMetric, ...]
    enrollments: tuple[EnrollmentRow, ...]


def _implicit_metric_set(org_id: str) -> dict[str, Any]:
    return {
        "apiVersion": "propel/v1",
        "kind": "MetricSet",
        "metadata": {"org": org_id},
        "spec": {"standard": {"mode": "default_on"}},
    }


def _standard_ids(
    metric_set: dict[str, Any],
    system_metrics: list[StoredDefinition],
) -> list[str]:
    standard = (metric_set.get("spec") or {}).get("standard") or {}
    mode = standard.get("mode", "default_on")
    disabled = set(standard.get("disabled") or [])
    enabled = list(standard.get("enabled") or [])
    all_ids = sorted(
        r.metric_id
        for r in system_metrics
        if r.status == "active" and r.metric_id.startswith("propel.")
    )
    if mode == "explicit":
        return [i for i in enabled if i in set(all_ids)]
    return [i for i in all_ids if i not in disabled]


def _custom_ids(metric_set: dict[str, Any]) -> list[str]:
    return list((metric_set.get("spec") or {}).get("custom") or [])


def _param_values_for(
    metric_set: dict[str, Any], metric_id: str
) -> dict[str, Any] | None:
    standard = (metric_set.get("spec") or {}).get("standard") or {}
    params = standard.get("params") or {}
    raw = params.get(metric_id)
    return dict(raw) if isinstance(raw, dict) else None


def _mapping_to_mapped_dim(doc: dict[str, Any]) -> MappedDim:
    spec = doc["spec"]
    mapping = tuple(
        sorted((str(k), str(v)) for k, v in (spec["mapping"] or {}).items())
    )
    default = spec.get("default", "other")
    if default is None:
        default = "other"
    return MappedDim(
        name=str(spec["to_dimension"]),
        from_field=str(spec["from_field"]),
        default=str(default),
        mapping=mapping,
    )


def load_org_mappings(store: DefinitionStore, org_id: str) -> dict[str, MappedDim]:
    """Index active DimensionMappings by to_dimension name and by mapping id."""
    out: dict[str, MappedDim] = {}
    for row in store.list_definitions(org_id, kind="DimensionMapping", status="active"):
        mapped = _mapping_to_mapped_dim(row.doc)
        out[mapped.name] = mapped
        out[row.metric_id] = mapped
    return out


# Back-compat alias for internal call sites.
_load_org_mappings = load_org_mappings


def _namespace(metric_id: str) -> str:
    return metric_id.split(".", 1)[0]


def _parent_org_for_extends(child_org: str, parent_id: str) -> str:
    ns = _namespace(parent_id)
    if ns == "propel":
        return SYSTEM_ORG
    return child_org


def _flatten_with_pins(
    store: DefinitionStore,
    row: StoredDefinition,
    *,
    org_id: str,
    depth: int = 0,
) -> dict[str, Any]:
    if depth > 3:
        raise ValueError(f"extends chain deeper than 3 for {row.metric_id}")
    doc = copy.deepcopy(row.doc)
    spec = doc.get("spec") or {}
    extends = spec.get("extends")
    if not extends:
        flat = copy.deepcopy(doc)
        flat.get("spec", {}).pop("extends", None)
        flat.get("spec", {}).pop("overrides", None)
        return flat

    pin = row.parent_pin
    parent_org = _parent_org_for_extends(org_id, extends)
    if pin and pin.get("metric_id") == extends:
        parent_row = store.get_definition(
            parent_org, extends, version=int(pin["version"])
        )
    else:
        parent_row = store.get_definition(parent_org, extends, status="active")
    if parent_row is None:
        raise ValueError(f"missing extends target {extends!r} for {row.metric_id}")

    parent_flat = _flatten_with_pins(store, parent_row, org_id=org_id, depth=depth + 1)
    # Reuse file merge by synthesizing by_id map
    by_id = {extends: parent_flat, row.metric_id: doc}
    return apply_extends(doc, by_id)


def _to_resolved_metric(
    metric_id: str,
    flat_doc: dict[str, Any],
    *,
    version: int,
) -> ResolvedMetric:
    meta = flat_doc.get("metadata") or {}
    spec = flat_doc["spec"]
    return ResolvedMetric(
        metric_id=metric_id,
        name=meta.get("name", metric_id),
        status=meta.get("status", "active"),
        version=version,
        definition_version=content_hash(spec),
        spec=spec,
        source_path=Path(f"<store:{metric_id}>"),
    )


def _select_mappings_for_dims(
    dimensions: list[str],
    mappings: dict[str, MappedDim],
) -> dict[str, MappedDim]:
    out: dict[str, MappedDim] = {}
    for dim in dimensions:
        if dim in mappings:
            # Prefer the MappedDim registered under the dimension name
            mapped = mappings[dim]
            out[mapped.name] = mapped
    return out


def resolve_org(
    store: DefinitionStore,
    org_id: str,
    *,
    catalog: dict[str, Any] | None = None,
    persist_enrollment: bool = True,
) -> OrgResolveResult:
    """Resolve the active MetricSet for ``org_id`` into CompiledPlans + enrollment."""
    _ = catalog or load_catalog()

    set_row = store.get_definition(org_id, METRIC_SET_ID, status="active")
    metric_set = set_row.doc if set_row is not None else _implicit_metric_set(org_id)

    system_metrics = store.list_active_system_metrics()
    std_ids = _standard_ids(metric_set, system_metrics)
    custom_ids = _custom_ids(metric_set)
    mappings = _load_org_mappings(store, org_id)

    # Flatten + bind params for all enrolled metrics into ResolvedMetric map
    resolved_docs: dict[
        str, tuple[StoredDefinition, dict[str, Any], dict[str, Any] | None]
    ] = {}

    for mid in std_ids:
        row = store.get_definition(SYSTEM_ORG, mid, status="active")
        if row is None:
            raise ValueError(f"missing active system metric {mid}")
        flat = _flatten_with_pins(store, row, org_id=org_id)
        params = _param_values_for(metric_set, mid)
        try:
            flat["spec"] = bind_params(flat["spec"], params)
        except ParamBindError:
            raise
        resolved_docs[mid] = (row, flat, params)

    for mid in custom_ids:
        row = store.get_definition(org_id, mid, status="active")
        if row is None:
            raise ValueError(f"missing active custom metric {org_id}/{mid}")
        flat = _flatten_with_pins(store, row, org_id=org_id)
        # Custom metrics don't take MetricSet standard.params; params on the
        # metric itself use defaults via bind_params(None).
        flat["spec"] = bind_params(flat["spec"], None)
        resolved_docs[mid] = (row, flat, None)

    by_resolved: dict[str, ResolvedMetric] = {}
    for mid, (row, flat, _params) in resolved_docs.items():
        by_resolved[mid] = _to_resolved_metric(mid, flat, version=row.version)

    # Operand refs may point at standards not in the enrollment set — load them
    # into the index with this org's param binding.
    def _ensure_operand(ref: str) -> None:
        if ref in by_resolved:
            return
        ns = _namespace(ref)
        defn_org = SYSTEM_ORG if ns == "propel" else org_id
        row = store.get_definition(defn_org, ref, status="active")
        if row is None:
            raise ValueError(f"missing operand ref {ref}")
        flat = _flatten_with_pins(store, row, org_id=org_id)
        params = _param_values_for(metric_set, ref) if ns == "propel" else None
        flat["spec"] = bind_params(flat["spec"], params)
        by_resolved[ref] = _to_resolved_metric(ref, flat, version=row.version)

    for _mid, (_row, flat, _p) in list(resolved_docs.items()):
        measure = (flat.get("spec") or {}).get("measure") or {}
        mtype = measure.get("type")
        if mtype == "ratio":
            for side in ("numerator", "denominator"):
                _ensure_operand(measure[side]["ref"])
        elif mtype == "formula":
            for _name, op in (measure.get("inputs") or {}).items():
                _ensure_operand(op["ref"])

    results: list[ResolvedOrgMetric] = []
    enrollments: list[EnrollmentRow] = []

    for mid in sorted(resolved_docs.keys()):
        row, flat, params = resolved_docs[mid]
        dims = list((flat.get("spec") or {}).get("dimensions") or [])
        mapped = _select_mappings_for_dims(dims, mappings)
        plan = build_compiled_plan(
            by_resolved[mid], by_resolved, mapped_dimensions=mapped or None
        )
        # Prefer semantic version int in plan.definition_version for store-backed
        # compiles while keeping hash separate.
        plan = CompiledPlan(
            metric_id=plan.metric_id,
            definition_version=str(row.version),
            kind=plan.kind,
            aggregations=plan.aggregations,
            expression=plan.expression,
            dimensions=plan.dimensions,
            grains=plan.grains,
            windows=plan.windows,
            zero_denominator=plan.zero_denominator,
        )
        digest = plan_content_hash(plan)
        resolved_json = plan_to_canonical_dict(plan)
        results.append(
            ResolvedOrgMetric(
                metric_id=mid,
                definition_org=row.org_id,
                definition_version=row.version,
                plan=plan,
                content_hash=digest,
                resolved_json=resolved_json,
                params=params,
                source_doc=flat,
            )
        )
        enrollments.append(
            EnrollmentRow(
                org_id=org_id,
                metric_id=mid,
                definition_org=row.org_id,
                definition_version=row.version,
                params_json=params,
                content_hash=digest,
            )
        )

    if persist_enrollment:
        store.replace_enrollments(org_id, enrollments)

    return OrgResolveResult(
        org_id=org_id,
        metrics=tuple(results),
        enrollments=tuple(enrollments),
    )
