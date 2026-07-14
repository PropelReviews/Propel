"""Tests for resolved-JSON structural diff."""

from __future__ import annotations

from propel_metrics.resolve.structural_diff import structural_diff, summarize_diff


def test_scalar_replace():
    changes = structural_diff({"a": 1}, {"a": 2})
    assert changes == [
        {"path": "$.a", "op": "replace", "before": 1, "after": 2},
    ]


def test_nested_add_remove():
    before = {"spec": {"filters": [{"field": "state", "op": "eq", "value": "merged"}]}}
    after = {
        "spec": {
            "filters": [
                {"field": "state", "op": "eq", "value": "merged"},
                {"field": "repo", "op": "eq", "value": "acme/core"},
            ],
            "visibility": "org",
        }
    }
    changes = structural_diff(before, after)
    paths = {c["path"] for c in changes}
    assert "$.spec.filters[1]" in paths
    assert "$.spec.visibility" in paths
    assert any(c["op"] == "add" for c in changes)


def test_identical_is_empty():
    doc = {"metadata": {"id": "a.b"}, "spec": {"measure": {"type": "count"}}}
    assert structural_diff(doc, doc) == []


def test_summarize_diff_lines():
    changes = structural_diff({"x": 1}, {"x": 2, "y": 3})
    lines = summarize_diff(changes)
    assert any("→" in line for line in lines)
    assert any("+" in line or "y" in line for line in lines)
