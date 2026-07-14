"""Classify authored YAML diffs as semantic vs non-semantic (revision-only)."""

from __future__ import annotations

import copy
from typing import Any, Literal

DiffKind = Literal["none", "non_semantic", "semantic"]

_NON_SEMANTIC_METADATA = frozenset({"name", "description", "tags", "owner", "advanced"})


def _strip_non_semantic(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    meta = dict(out.get("metadata") or {})
    for key in list(meta):
        if key in _NON_SEMANTIC_METADATA:
            meta.pop(key, None)
    # version/status/revision are store-owned; ignore for semantic compare of body
    for key in ("version", "status", "revision"):
        meta.pop(key, None)
    out["metadata"] = meta
    spec = dict(out.get("spec") or {})
    spec.pop("display", None)
    out["spec"] = spec
    return out


def classify_doc_diff(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> DiffKind:
    """Return whether current differs from previous, and how."""
    if previous is None:
        return "semantic"
    if previous == current:
        return "none"
    if _strip_non_semantic(previous) == _strip_non_semantic(current):
        return "non_semantic"
    return "semantic"
