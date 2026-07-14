"""Org resolve + param binding tests (M4)."""

from __future__ import annotations

import copy

import pytest
import yaml
from propel_metrics.resolve.org import resolve_org
from propel_metrics.resolve.params import ParamBindError, bind_params
from propel_metrics.resolve.semantic_diff import classify_doc_diff
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import METRIC_SET_ID


def test_bind_params_applies_default_and_strips_decls() -> None:
    spec = {
        "entity": "release",
        "filters": [{"field": "is_draft", "op": "eq", "value": False}],
        "params": {
            "include_prereleases": {
                "type": "boolean",
                "default": False,
                "binds": {"filter": {"field": "is_prerelease", "op": "eq"}},
            }
        },
        "measure": {"type": "count"},
        "time": {"field": "published_at", "grains": ["day"]},
    }
    out = bind_params(spec, None)
    assert "params" not in out
    assert out["filters"][-1] == {
        "field": "is_prerelease",
        "op": "eq",
        "value": False,
    }


def test_bind_params_rejects_unknown() -> None:
    spec = {
        "params": {
            "x": {
                "type": "string",
                "default": "a",
                "binds": {"filter": {"field": "repo", "op": "eq"}},
            }
        }
    }
    with pytest.raises(ParamBindError) as ei:
        bind_params(spec, {"y": "z"})
    assert ei.value.code == "E_UNKNOWN_PARAM"


def test_semantic_diff_display_only() -> None:
    base = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {"id": "acme.x", "name": "X", "version": 1},
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "time": {"field": "merged_at", "grains": ["day"]},
            "display": {"unit": "count"},
        },
    }
    edited = copy.deepcopy(base)
    edited["metadata"]["name"] = "Renamed"
    edited["spec"]["display"] = {"unit": "count", "format": "integer"}
    assert classify_doc_diff(base, edited) == "non_semantic"
    edited2 = copy.deepcopy(base)
    edited2["spec"]["filters"] = [{"field": "state", "op": "eq", "value": "merged"}]
    assert classify_doc_diff(base, edited2) == "semantic"


def _metric_set(org: str, **spec_extra):
    return {
        "apiVersion": "propel/v1",
        "kind": "MetricSet",
        "metadata": {"org": org},
        "spec": spec_extra,
    }


def test_resolve_org_default_on_shared_hash() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    store.put_metric_doc("acme", _metric_set("acme", standard={"mode": "default_on"}))
    store.set_status("acme", METRIC_SET_ID, 1, "active")
    store.put_metric_doc("beta", _metric_set("beta", standard={"mode": "default_on"}))
    store.set_status("beta", METRIC_SET_ID, 1, "active")

    acme = resolve_org(store, "acme")
    beta = resolve_org(store, "beta")
    acme_by = {m.metric_id: m for m in acme.metrics}
    beta_by = {m.metric_id: m for m in beta.metrics}
    assert "propel.deployment_frequency" in acme_by
    assert (
        acme_by["propel.deployment_frequency"].content_hash
        == beta_by["propel.deployment_frequency"].content_hash
    )
    assert len(store.list_enrollments("acme")) == len(acme.metrics)


def test_resolve_org_explicit_and_disabled() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    store.put_metric_doc(
        "acme",
        _metric_set(
            "acme",
            standard={
                "mode": "explicit",
                "enabled": ["propel.merged_prs", "propel.deployment_frequency"],
            },
        ),
    )
    store.set_status("acme", METRIC_SET_ID, 1, "active")
    result = resolve_org(store, "acme")
    ids = {m.metric_id for m in result.metrics}
    assert ids == {"propel.merged_prs", "propel.deployment_frequency"}


def test_param_override_changes_hash() -> None:
    store = MemoryDefinitionStore()
    imported = import_system_metrics(store)
    # Patch deployment_frequency with a param decl in the store copy
    row = store.get_definition(
        "__system", "propel.deployment_frequency", status="active"
    )
    assert row is not None
    doc = copy.deepcopy(row.doc)
    doc["spec"]["params"] = {
        "include_prereleases": {
            "type": "boolean",
            "default": False,
            "binds": {"filter": {"field": "is_prerelease", "op": "eq"}},
        }
    }
    store.put_metric_doc(
        "__system",
        doc,
        yaml_text=yaml.safe_dump(doc),
        status="active",
        version=row.version,
        content_hash=row.content_hash,
        resolved_json=row.resolved_json,
    )

    store.put_metric_doc(
        "acme",
        _metric_set(
            "acme",
            standard={
                "mode": "explicit",
                "enabled": ["propel.deployment_frequency"],
                "params": {
                    "propel.deployment_frequency": {"include_prereleases": True}
                },
            },
        ),
    )
    store.set_status("acme", METRIC_SET_ID, 1, "active")
    store.put_metric_doc(
        "beta",
        _metric_set(
            "beta",
            standard={
                "mode": "explicit",
                "enabled": ["propel.deployment_frequency"],
            },
        ),
    )
    store.set_status("beta", METRIC_SET_ID, 1, "active")

    acme = resolve_org(store, "acme")
    beta = resolve_org(store, "beta")
    a = next(m for m in acme.metrics if m.metric_id == "propel.deployment_frequency")
    b = next(m for m in beta.metrics if m.metric_id == "propel.deployment_frequency")
    assert a.content_hash != b.content_hash
    assert {"field": "is_prerelease", "op": "eq", "value": True} in a.plan.aggregations[
        "value"
    ].operand.filters
    _ = imported


def test_custom_ratio_with_mapped_team() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)

    mapping = {
        "apiVersion": "propel/v1",
        "kind": "DimensionMapping",
        "metadata": {"id": "acme.author_to_team"},
        "spec": {
            "entity": "pull_request",
            "from_field": "author_id",
            "to_dimension": "team",
            "default": "other",
            "mapping": {"alice": "platform", "bob": "growth"},
        },
    }
    store.put_metric_doc("acme", mapping, status="active")

    custom = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {
            "id": "acme.unreviewed_merge_rate",
            "name": "Unreviewed merge rate",
            "status": "active",
            "version": 1,
        },
        "spec": {
            "entity": "pull_request",
            "measure": {
                "type": "ratio",
                "numerator": {
                    "ref": "propel.reverted_prs",
                },
                "denominator": {"ref": "propel.merged_prs"},
                "zero_denominator": None,
            },
            "time": {"field": "merged_at", "grains": ["week"]},
            "dimensions": ["team"],
            "visibility": "org",
        },
    }
    # Ratio metrics still need time on the derived metric; operands bring entities.
    # Our IR uses parent specs for time_field — derived time.field is unused for
    # ratio operands. Keep schema-valid shape.
    store.put_metric_doc("acme", custom, status="active")
    store.put_metric_doc(
        "acme",
        _metric_set(
            "acme",
            standard={"mode": "explicit", "enabled": []},
            custom=["acme.unreviewed_merge_rate"],
        ),
        version=1,
    )
    # MetricSet put may collide version — force active
    store.set_status("acme", METRIC_SET_ID, 1, "active")

    result = resolve_org(store, "acme")
    assert len(result.metrics) == 1
    m = result.metrics[0]
    assert m.metric_id == "acme.unreviewed_merge_rate"
    assert m.plan.dimensions == ("team",)
    mapped = m.plan.aggregations["num"].operand.mapped_dimensions
    assert mapped and mapped[0].name == "team"
    assert mapped[0].mapping[0] == ("alice", "platform")
