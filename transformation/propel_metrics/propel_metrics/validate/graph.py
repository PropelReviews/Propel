"""Graph validation: refs, extends, cycles, derived-of-derived."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from propel_metrics.validate.errors import ValidationResult

_DERIVED_TYPES = {"ratio", "formula"}


def _metric_id(doc: dict[str, Any]) -> str | None:
    return (doc.get("metadata") or {}).get("id")


def _namespace(metric_id: str) -> str:
    return metric_id.split(".", 1)[0]


def _operand_refs(measure: dict[str, Any] | None) -> list[tuple[str, str]]:
    """Return (json_path, ref_id) for ratio/formula operands."""
    if not measure:
        return []
    mtype = measure.get("type")
    refs: list[tuple[str, str]] = []
    if mtype == "ratio":
        for side in ("numerator", "denominator"):
            op = measure.get(side) or {}
            if "ref" in op:
                refs.append((f"spec.measure.{side}.ref", op["ref"]))
    elif mtype == "formula":
        for name, op in (measure.get("inputs") or {}).items():
            if "ref" in op:
                refs.append((f"spec.measure.inputs.{name}.ref", op["ref"]))
    return refs


def _is_derived(doc: dict[str, Any]) -> bool:
    measure = (doc.get("spec") or {}).get("measure") or {}
    return measure.get("type") in _DERIVED_TYPES


def validate_graph(
    docs: list[tuple[Path, dict[str, Any]]],
) -> ValidationResult:
    result = ValidationResult()
    metrics: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path, doc in docs:
        if doc.get("kind") != "Metric":
            continue
        mid = _metric_id(doc)
        if not mid:
            continue
        if mid in metrics:
            result.error(
                "E_DUPLICATE_ID",
                "metadata.id",
                f"duplicate metric id {mid!r}",
                file=str(path),
            )
        metrics[mid] = (path, doc)

    # extends checks
    for path, doc in docs:
        if doc.get("kind") != "Metric":
            continue
        mid = _metric_id(doc)
        spec = doc.get("spec") or {}
        extends = spec.get("extends")
        if not extends:
            if "overrides" in spec:
                result.error(
                    "E_OVERRIDES_WITHOUT_EXTENDS",
                    "spec.overrides",
                    "overrides requires extends",
                    file=str(path),
                )
            continue

        if extends not in metrics:
            result.error(
                "E_MISSING_REF",
                "spec.extends",
                f"extends target {extends!r} not found",
                file=str(path),
            )
            continue

        parent_path, parent = metrics[extends]
        parent_status = (parent.get("metadata") or {}).get("status", "draft")
        if parent_status in {"draft", "archived"}:
            result.error(
                "E_EXTENDS_STATUS",
                "spec.extends",
                f"cannot extend {extends!r} with status {parent_status!r}",
                file=str(path),
            )

        # cross-namespace: only org → propel
        if mid and _namespace(mid) == "propel" and _namespace(extends) != "propel":
            result.error(
                "E_EXTENDS_NAMESPACE",
                "spec.extends",
                "propel.* metrics cannot extend org-namespaced parents",
                file=str(path),
            )
        if (
            mid
            and _namespace(mid) != "propel"
            and _namespace(extends) != "propel"
            and _namespace(mid) != _namespace(extends)
        ):
            result.error(
                "E_EXTENDS_NAMESPACE",
                "spec.extends",
                "cross-org extends is not allowed",
                file=str(path),
            )

        # depth
        depth = 1
        cursor = extends
        seen = {mid, extends}
        while cursor:
            _p_path, pdoc = metrics.get(cursor, (parent_path, {}))
            next_ext = (pdoc.get("spec") or {}).get("extends")
            if not next_ext:
                break
            depth += 1
            if depth > 3:
                result.error(
                    "E_EXTENDS_DEPTH",
                    "spec.extends",
                    "extends chain deeper than 3",
                    file=str(path),
                )
                break
            if next_ext in seen:
                result.error(
                    "E_CYCLE",
                    "spec.extends",
                    f"cycle detected via {next_ext!r}",
                    file=str(path),
                )
                break
            seen.add(next_ext)
            if next_ext not in metrics:
                break
            cursor = next_ext

    # operand refs + derived-of-derived
    for path, doc in docs:
        if doc.get("kind") != "Metric":
            continue
        measure = (doc.get("spec") or {}).get("measure") or {}
        for jpath, ref in _operand_refs(measure):
            if ref not in metrics:
                result.error(
                    "E_MISSING_REF",
                    jpath,
                    f"operand ref {ref!r} not found",
                    file=str(path),
                )
                continue
            _rpath, rdoc = metrics[ref]
            if _is_derived(rdoc):
                result.error(
                    "E_DERIVED_NESTING",
                    jpath,
                    "derived-of-derived is not allowed in v1 "
                    f"({ref!r} is ratio/formula)",
                    file=str(path),
                )
            rstatus = (rdoc.get("metadata") or {}).get("status", "draft")
            if rstatus in {"draft", "archived"}:
                result.error(
                    "E_REF_STATUS",
                    jpath,
                    f"operand {ref!r} has status {rstatus!r}",
                    file=str(path),
                )

    return result
