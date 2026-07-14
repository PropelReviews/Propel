"""Structural diff of two JSON-compatible values (resolved metric docs).

Returns a list of change records suitable for Versions / activate UIs.
Paths use JSON-pointer-ish dotted segments (e.g. ``spec.filters[0].op``).
"""

from __future__ import annotations

from typing import Any


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def structural_diff(
    before: Any,
    after: Any,
    *,
    path: str = "$",
) -> list[dict[str, Any]]:
    """Return structural changes between ``before`` and ``after``.

    Each item: ``{path, op: add|remove|replace, before?, after?}``.
    """
    if before == after:
        return []

    if _is_scalar(before) or _is_scalar(after):
        if before is None and after is not None:
            return [{"path": path, "op": "add", "after": after}]
        if after is None and before is not None:
            return [{"path": path, "op": "remove", "before": before}]
        return [{"path": path, "op": "replace", "before": before, "after": after}]

    if isinstance(before, list) and isinstance(after, list):
        changes: list[dict[str, Any]] = []
        # Prefer element-wise when lengths match; otherwise replace whole list
        # when order-sensitive identity is unclear (filters / grains).
        max_len = max(len(before), len(after))
        if abs(len(before) - len(after)) > 0 and not (
            all(_is_scalar(x) for x in before + after)
        ):
            # Still walk common prefix then add/remove tails for readability.
            for i in range(min(len(before), len(after))):
                changes.extend(
                    structural_diff(before[i], after[i], path=f"{path}[{i}]")
                )
            for i in range(len(before), len(after)):
                changes.append({"path": f"{path}[{i}]", "op": "add", "after": after[i]})
            for i in range(len(after), len(before)):
                changes.append(
                    {"path": f"{path}[{i}]", "op": "remove", "before": before[i]}
                )
            return changes

        for i in range(max_len):
            child = f"{path}[{i}]"
            if i >= len(before):
                changes.append({"path": child, "op": "add", "after": after[i]})
            elif i >= len(after):
                changes.append({"path": child, "op": "remove", "before": before[i]})
            else:
                changes.extend(structural_diff(before[i], after[i], path=child))
        return changes

    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        keys = sorted(set(before) | set(after), key=str)
        for key in keys:
            child = f"{path}.{key}" if path != "$" else f"$.{key}"
            if key not in before:
                changes.append({"path": child, "op": "add", "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "op": "remove", "before": before[key]})
            else:
                changes.extend(structural_diff(before[key], after[key], path=child))
        return changes

    # Type mismatch (e.g. list vs dict)
    return [{"path": path, "op": "replace", "before": before, "after": after}]


def summarize_diff(changes: list[dict[str, Any]]) -> list[str]:
    """Human-readable one-liners for activate / versions sheets."""
    lines: list[str] = []
    for c in changes:
        op = c["op"]
        p = c["path"]
        if op == "add":
            lines.append(f"{p}: + {c.get('after')!r}")
        elif op == "remove":
            lines.append(f"{p}: - {c.get('before')!r}")
        else:
            lines.append(f"{p}: {c.get('before')!r} → {c.get('after')!r}")
    return lines
