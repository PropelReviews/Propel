"""Broader semantic / graph edge cases for the config format."""

from __future__ import annotations

from pathlib import Path

import yaml
from propel_metrics.validate import validate


def _write(tmp_path: Path, name: str, doc: dict) -> Path:
    path = tmp_path / name
    path.write_text(yaml.dump(doc), encoding="utf-8")
    return path


def test_interval_requires_event_time_fields(tmp_path: Path) -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.bad_interval", "name": "Bad", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {
                "type": "interval",
                "from": "repo",
                "to": "merged_at",
                "agg": "avg",
            },
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    result = validate([_write(tmp_path, "bad.yaml", doc)])
    assert any(e.code == "E_FIELD_ROLE" for e in result.errors)


def test_ratio_must_omit_time_field(tmp_path: Path) -> None:
    base = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "acme.base", "name": "Base", "status": "active"},
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
                "numerator": {"ref": "acme.base"},
                "denominator": {"ref": "acme.base"},
            },
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    result = validate(
        [_write(tmp_path, "base.yaml", base), _write(tmp_path, "ratio.yaml", ratio)]
    )
    assert any(e.code == "E_TIME_FIELD" for e in result.errors)


def test_sql_measure_requires_advanced(tmp_path: Path) -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.sqlish", "name": "Sqlish", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "sql", "sql": "count(*)"},
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    result = validate([_write(tmp_path, "sql.yaml", doc)])
    assert any(e.code == "E_ADVANCED_REQUIRED" for e in result.errors)


def test_extends_draft_parent_rejected(tmp_path: Path) -> None:
    parent = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.draft_parent", "name": "Draft", "status": "draft"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    child = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.draft_child", "name": "Child", "status": "active"},
        "spec": {
            "extends": "propel.draft_parent",
            "overrides": {"display": {"unit": "count"}},
        },
    }
    result = validate(
        [
            _write(tmp_path, "parent.yaml", parent),
            _write(tmp_path, "child.yaml", child),
        ]
    )
    assert any(e.code == "E_EXTENDS_STATUS" for e in result.errors)


def test_in_list_empty_rejected(tmp_path: Path) -> None:
    doc = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "propel.empty_in", "name": "Empty", "status": "active"},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "filters": [{"field": "repo", "op": "in", "value": []}],
            "time": {"field": "merged_at", "grains": ["day"]},
        },
    }
    result = validate([_write(tmp_path, "empty.yaml", doc)])
    # empty array may fail schema and/or semantic
    assert not result.ok
    assert any(e.code in {"E_SCHEMA", "E_VALUE_TYPE"} for e in result.errors)
