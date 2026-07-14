"""Validator tests for shipped configs and negative fixtures."""

from __future__ import annotations

from pathlib import Path

import yaml
from propel_metrics.validate import validate
from propel_metrics.validate.structural import validate_document_structure


def test_shipped_configs_validate() -> None:
    result = validate()
    assert result.ok, "\n".join(e.format() for e in result.errors)


def test_unknown_key_rejected() -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.x", "name": "X", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "time": {"field": "merged_at", "grains": ["day"]},
            "filtres": [],  # typo
        },
    }
    result = validate_document_structure(doc, file="mem.yaml")
    assert not result.ok
    assert any(e.code == "E_SCHEMA" for e in result.errors)


def test_bad_op_type(tmp_path: Path) -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.bad_op", "name": "Bad", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "filters": [{"field": "repo", "op": "gt", "value": 1}],
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    path = tmp_path / "bad_op.yaml"
    path.write_text(yaml.dump(doc), encoding="utf-8")
    result = validate([path])
    assert any(e.code == "E_OP_TYPE" for e in result.errors)


def test_missing_extends_target(tmp_path: Path) -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.orphan", "name": "Orphan", "status": "active"},
        "spec": {
            "extends": "propel.does_not_exist",
            "overrides": {"measure": {"agg": "avg"}},
        },
    }
    path = tmp_path / "orphan.yaml"
    path.write_text(yaml.dump(doc), encoding="utf-8")
    # Include shipped configs so structural/schema for other files still works,
    # but validate only this file for the missing ref.
    result = validate([path])
    assert any(e.code == "E_MISSING_REF" for e in result.errors)


def test_derived_nesting_rejected(tmp_path: Path) -> None:
    base = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "acme.base_count", "name": "Base", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    ratio = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "acme.ratio", "name": "Ratio", "status": "active"},
        "spec": {
            "measure": {
                "type": "ratio",
                "numerator": {"ref": "acme.base_count"},
                "denominator": {"ref": "acme.base_count"},
            },
            "time": {"grains": ["day"]},
        },
    }
    nested = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "acme.nested", "name": "Nested", "status": "active"},
        "spec": {
            "measure": {
                "type": "ratio",
                "numerator": {"ref": "acme.ratio"},
                "denominator": {"ref": "acme.base_count"},
            },
            "time": {"grains": ["day"]},
        },
    }
    paths = []
    for name, doc in [
        ("base.yaml", base),
        ("ratio.yaml", ratio),
        ("nested.yaml", nested),
    ]:
        p = tmp_path / name
        p.write_text(yaml.dump(doc), encoding="utf-8")
        paths.append(p)
    result = validate(paths)
    assert any(e.code == "E_DERIVED_NESTING" for e in result.errors)
