"""Resolve extends chains and content-hash metric definitions for compile."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from propel_metrics.validate.loader import load_documents


@dataclass(frozen=True, slots=True)
class ResolvedMetric:
    metric_id: str
    name: str
    status: str
    version: int
    definition_version: str  # content hash (short)
    spec: dict[str, Any]
    source_path: Path


def _deep_merge_measure(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """Shallow-merge scalar measure params; type is not overridable."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key == "type":
            continue
        out[key] = copy.deepcopy(value)
    return out


def apply_extends(
    doc: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return a Metric document with extends flattened into a concrete spec."""
    spec = doc.get("spec") or {}
    extends = spec.get("extends")
    if not extends:
        resolved = copy.deepcopy(doc)
        resolved.get("spec", {}).pop("extends", None)
        resolved.get("spec", {}).pop("overrides", None)
        return resolved

    parent = by_id[extends]
    parent_resolved = apply_extends(parent, by_id)
    merged = copy.deepcopy(parent_resolved)
    merged["metadata"] = copy.deepcopy(doc["metadata"])

    parent_spec = copy.deepcopy(parent_resolved["spec"])
    overrides = copy.deepcopy(spec.get("overrides") or {})
    # Top-level keys on child spec (other than extends/overrides) act as overrides too
    for key, value in spec.items():
        if key in {"extends", "overrides"}:
            continue
        overrides[key] = value

    # entity / time.field not overridable
    overrides.pop("entity", None)
    if "time" in overrides and isinstance(overrides["time"], dict):
        overrides["time"].pop("field", None)
        if not overrides["time"]:
            overrides.pop("time")

    if "measure" in overrides and "measure" in parent_spec:
        parent_spec["measure"] = _deep_merge_measure(
            parent_spec["measure"], overrides.pop("measure")
        )
    elif "measure" in overrides:
        parent_spec["measure"] = overrides.pop("measure")

    if "filters" in overrides:
        parent_filters = list(parent_spec.get("filters") or [])
        parent_filters.extend(overrides.pop("filters") or [])
        parent_spec["filters"] = parent_filters

    if "time" in overrides:
        ptime = dict(parent_spec.get("time") or {})
        otime = overrides.pop("time")
        if "grains" in otime:
            ptime["grains"] = otime["grains"]
        if "windows" in otime:
            ptime["windows"] = otime["windows"]
        parent_spec["time"] = ptime

    for key in ("dimensions", "display", "visibility", "params"):
        if key in overrides:
            parent_spec[key] = overrides.pop(key)

    # ignore any remaining unknown override keys (validation should have caught)
    merged["spec"] = parent_spec
    return merged


def content_hash(spec: dict[str, Any]) -> str:
    """Stable short hash of the semantic spec (excludes display-only keys).

    Used by the file-based compile inventory as ``definition_version``.
    M4 shared-model / dirty tracking uses ``plan_content_hash`` (full sha256 of
    the canonical CompiledPlan JSON) instead.
    """
    semantic = {
        "entity": spec.get("entity"),
        "measure": spec.get("measure"),
        "filters": spec.get("filters"),
        "time": {
            "field": (spec.get("time") or {}).get("field"),
            "grains": (spec.get("time") or {}).get("grains"),
            "windows": (spec.get("time") or {}).get("windows"),
        },
        "dimensions": spec.get("dimensions"),
        "params": spec.get("params"),
        "visibility": spec.get("visibility"),
    }
    payload = json.dumps(semantic, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def resolve_metrics(
    paths: list[Path] | None = None,
    *,
    active_only: bool = True,
) -> list[ResolvedMetric]:
    docs = load_documents(paths)
    by_id = {
        (d.get("metadata") or {}).get("id"): d
        for _, d in docs
        if d.get("kind") == "Metric" and (d.get("metadata") or {}).get("id")
    }
    path_by_id = {
        (d.get("metadata") or {}).get("id"): p
        for p, d in docs
        if d.get("kind") == "Metric"
    }

    resolved: list[ResolvedMetric] = []
    for mid, doc in sorted(by_id.items()):
        meta = doc.get("metadata") or {}
        status = meta.get("status", "draft")
        if active_only and status not in {"active", "deprecated"}:
            continue
        flat = apply_extends(doc, by_id)
        spec = flat["spec"]
        # Skip derived types in M2 compile set — still resolvable for tests
        resolved.append(
            ResolvedMetric(
                metric_id=mid,
                name=meta.get("name", mid),
                status=status,
                version=int(meta.get("version", 1)),
                definition_version=content_hash(spec),
                spec=spec,
                source_path=path_by_id[mid],
            )
        )
    return resolved
