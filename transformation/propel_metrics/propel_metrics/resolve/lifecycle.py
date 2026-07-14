"""Activate / archive / repin flows against a DefinitionStore."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.ir.hashutil import plan_content_hash, plan_to_canonical_dict
from propel_metrics.ir.types import CompiledPlan
from propel_metrics.resolve import ResolvedMetric, apply_extends, content_hash
from propel_metrics.resolve.org import resolve_org
from propel_metrics.resolve.params import bind_params
from propel_metrics.resolve.pins import parent_pin_from_active, stale_pin
from propel_metrics.resolve.semantic_diff import classify_doc_diff
from propel_metrics.store.protocol import (
    METRIC_SET_ID,
    SYSTEM_ORG,
    DefinitionNotice,
    DefinitionStore,
    StoredDefinition,
)
from propel_metrics.validate import validate
from propel_metrics.validate.loader import load_catalog


def _namespace(metric_id: str) -> str:
    return metric_id.split(".", 1)[0]


def _parent_org(child_org: str, parent_id: str) -> str:
    return SYSTEM_ORG if _namespace(parent_id) == "propel" else child_org


def validate_yaml_text(yaml_text: str) -> list[dict[str, Any]]:
    """Validate a single YAML document; return structured error dicts."""
    import tempfile

    from propel_metrics.paths import PROPEL_CONFIGS_DIR
    from propel_metrics.validate.loader import load_documents

    doc = yaml.safe_load(yaml_text)
    if not isinstance(doc, dict):
        return [{"code": "E_YAML", "path": "$", "message": "root must be a mapping"}]

    mid = (doc.get("metadata") or {}).get("id")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.yaml"
        path.write_text(yaml_text, encoding="utf-8")
        # Include shipped propel.* configs for extends/operand resolution, but
        # skip any file that shares this document's id (avoids E_DUPLICATE_ID
        # when activating an updated propel.* definition).
        extra: list[Path] = []
        for cfg_path, cfg_doc in load_documents([PROPEL_CONFIGS_DIR]):
            cfg_id = (cfg_doc.get("metadata") or {}).get("id")
            if mid and cfg_id == mid:
                continue
            extra.append(cfg_path)
        result = validate([path, *extra])
    return [
        {"code": e.code, "path": e.path, "message": e.message, "file": e.file}
        for e in result.errors
    ]


def _build_plan_for_doc(
    store: DefinitionStore,
    org_id: str,
    doc: dict[str, Any],
    *,
    version: int,
    parent_pin: dict[str, Any] | None,
) -> tuple[CompiledPlan, str, dict[str, Any]]:
    mid = (doc.get("metadata") or {}).get("id")
    if not mid:
        raise ValueError("metric metadata.id required")

    # Materialize a temporary ResolvedMetric index from store + this doc
    by_docs: dict[str, dict[str, Any]] = {mid: doc}
    # Load active system + org metrics for operand refs
    for row in store.list_active_system_metrics():
        by_docs.setdefault(row.metric_id, row.doc)
    for row in store.list_definitions(org_id, kind="Metric", status="active"):
        by_docs.setdefault(row.metric_id, row.doc)

    # Flatten extends using pins when present
    flat_doc = copy.deepcopy(doc)
    extends = (flat_doc.get("spec") or {}).get("extends")
    if extends:
        parent_org = _parent_org(org_id, extends)
        if parent_pin and parent_pin.get("metric_id") == extends:
            parent_row = store.get_definition(
                parent_org, extends, version=int(parent_pin["version"])
            )
        else:
            parent_row = store.get_definition(parent_org, extends, status="active")
        if parent_row is None:
            raise ValueError(f"missing parent {extends}")
        by_docs[extends] = parent_row.doc
        flat_doc = apply_extends(doc, by_docs)

    flat_doc["spec"] = bind_params(flat_doc["spec"], None)
    by_resolved: dict[str, ResolvedMetric] = {}
    for rid, rdoc in by_docs.items():
        rflat = rdoc
        if rid == mid:
            rflat = flat_doc
        elif (rdoc.get("spec") or {}).get("extends"):
            rflat = apply_extends(rdoc, by_docs)
        rspec = bind_params(copy.deepcopy(rflat["spec"]), None)
        meta = rflat.get("metadata") or {}
        by_resolved[rid] = ResolvedMetric(
            metric_id=rid,
            name=meta.get("name", rid),
            status=meta.get("status", "active"),
            version=int(meta.get("version", 1)),
            definition_version=content_hash(rspec),
            spec=rspec,
            source_path=Path(f"<store:{rid}>"),
        )

    metric = by_resolved[mid]
    # Remap definition_version for hashing alignment with org resolve
    plan = build_compiled_plan(metric, by_resolved)
    plan = CompiledPlan(
        metric_id=plan.metric_id,
        definition_version=str(version),
        kind=plan.kind,
        aggregations=plan.aggregations,
        expression=plan.expression,
        dimensions=plan.dimensions,
        grains=plan.grains,
        windows=plan.windows,
        zero_denominator=plan.zero_denominator,
    )
    digest = plan_content_hash(plan)
    return plan, digest, plan_to_canonical_dict(plan)


def save_draft(
    store: DefinitionStore,
    *,
    org_id: str,
    yaml_text: str,
    created_by: str,
    catalog_version: str | None = None,
) -> StoredDefinition:
    """Create or bump a draft definition from authored YAML."""
    doc = yaml.safe_load(yaml_text)
    if not isinstance(doc, dict):
        raise ValueError("YAML root must be a mapping")
    kind = doc["kind"]
    mid = METRIC_SET_ID if kind == "MetricSet" else (doc.get("metadata") or {})["id"]

    existing_any = store.get_definition(org_id, mid)
    prev_doc = existing_any.doc if existing_any else None
    diff = classify_doc_diff(prev_doc, doc)

    catalog = load_catalog()
    cat_ver = catalog_version or str(catalog.get("catalogVersion", "1"))

    if existing_any and diff == "non_semantic":
        # Bump revision in place on the latest version row
        row = existing_any
        row.revision = row.revision + 1
        row.yaml = yaml_text
        row.doc = doc
        return store.upsert_definition(row)

    if existing_any and diff == "none":
        return existing_any

    new_version = 1
    if existing_any:
        new_version = existing_any.version + 1

    parent_pin = None
    extends = (doc.get("spec") or {}).get("extends")
    if extends and kind == "Metric":
        parent_org = _parent_org(org_id, extends)
        parent_pin = parent_pin_from_active(store, extends, parent_org=parent_org)

    row = StoredDefinition(
        org_id=org_id,
        metric_id=mid,
        version=new_version,
        revision=1,
        kind=kind,
        yaml=yaml_text,
        doc=doc,
        status="draft",
        parent_pin=parent_pin,
        catalog_version=cat_ver,
        created_by=created_by,
    )
    return store.upsert_definition(row)


def activate(
    store: DefinitionStore,
    *,
    org_id: str,
    metric_id: str,
    version: int | None = None,
    known_orgs: list[str] | None = None,
) -> StoredDefinition:
    """Activate a draft (or specified version): deprecate prior active, mark dirty."""
    if version is None:
        row = store.get_definition(org_id, metric_id)
        if row is None or row.status != "draft":
            # allow activating latest draft specifically
            drafts = [
                r
                for r in store.list_definitions(org_id, status="draft")
                if r.metric_id == metric_id
            ]
            if not drafts:
                raise ValueError(f"no draft to activate for {org_id}/{metric_id}")
            row = max(drafts, key=lambda r: r.version)
    else:
        row = store.get_definition(org_id, metric_id, version=version)
        if row is None:
            raise ValueError(f"missing {org_id}/{metric_id}@{version}")

    errors = validate_yaml_text(row.yaml)
    if errors:
        raise ValueError(f"validation failed: {errors}")

    # Deprecate current active/broken
    current = store.get_definition(org_id, metric_id, status="active")
    if current is None:
        current = store.get_definition(org_id, metric_id, status="broken")
    if current is not None and (
        current.version != row.version or current.org_id != row.org_id
    ):
        store.set_status(org_id, metric_id, current.version, "deprecated")

    # Refresh parent_pin to currently active parent at activation time
    extends = (row.doc.get("spec") or {}).get("extends")
    if extends and row.kind == "Metric":
        parent_org = _parent_org(org_id, extends)
        row.parent_pin = parent_pin_from_active(store, extends, parent_org=parent_org)

    if row.kind == "Metric":
        _plan, digest, resolved = _build_plan_for_doc(
            store,
            org_id,
            row.doc,
            version=row.version,
            parent_pin=row.parent_pin,
        )
        row.resolved_json = resolved
        row.content_hash = digest
        store.mark_dirty(digest, reason=f"activate:{org_id}/{metric_id}@{row.version}")

    row.status = "active"
    stored = store.upsert_definition(row)

    # Fan out parent_version_available notices when activating a parent
    if row.kind == "Metric" and known_orgs:
        for child_org in known_orgs:
            for child in store.list_definitions(
                child_org, kind="Metric", status="active"
            ):
                if stale_pin(
                    child,
                    parent_metric_id=metric_id,
                    new_parent_version=row.version,
                ):
                    store.add_notice(
                        DefinitionNotice(
                            org_id=child_org,
                            metric_id=child.metric_id,
                            notice="parent_version_available",
                            payload={
                                "parent_metric_id": metric_id,
                                "parent_org": org_id,
                                "new_version": row.version,
                                "pinned_version": (child.parent_pin or {}).get(
                                    "version"
                                ),
                            },
                        )
                    )

    # Refresh enrollment for this org when MetricSet or Metric changes
    if org_id != SYSTEM_ORG:
        resolve_org(store, org_id, persist_enrollment=True)
    elif known_orgs:
        for o in known_orgs:
            resolve_org(store, o, persist_enrollment=True)

    return stored


def archive(
    store: DefinitionStore,
    *,
    org_id: str,
    metric_id: str,
) -> StoredDefinition:
    row = store.get_definition(org_id, metric_id, status="active")
    if row is None:
        row = store.get_definition(org_id, metric_id)
    if row is None:
        raise ValueError(f"missing {org_id}/{metric_id}")
    store.set_status(org_id, metric_id, row.version, "archived")
    row.status = "archived"
    if org_id != SYSTEM_ORG:
        resolve_org(store, org_id, persist_enrollment=True)
    return row


def repin(
    store: DefinitionStore,
    *,
    org_id: str,
    metric_id: str,
    activate_after: bool = True,
    created_by: str = "system",
) -> StoredDefinition:
    """Create a new child version pinned to the parent's current active version."""
    child = store.get_definition(org_id, metric_id, status="active")
    if child is None:
        raise ValueError(f"no active child {org_id}/{metric_id}")
    extends = (child.doc.get("spec") or {}).get("extends")
    if not extends:
        raise ValueError(f"{metric_id} does not extend a parent")
    parent_org = _parent_org(org_id, extends)
    new_pin = parent_pin_from_active(store, extends, parent_org=parent_org)
    if child.parent_pin == new_pin:
        return child

    new_version = child.version + 1
    doc = copy.deepcopy(child.doc)
    doc["metadata"] = dict(doc.get("metadata") or {})
    doc["metadata"]["version"] = new_version
    doc["metadata"]["status"] = "draft"
    yaml_text = yaml.safe_dump(doc, sort_keys=False)

    draft = StoredDefinition(
        org_id=org_id,
        metric_id=metric_id,
        version=new_version,
        revision=1,
        kind="Metric",
        yaml=yaml_text,
        doc=doc,
        status="draft",
        parent_pin=new_pin,
        catalog_version=child.catalog_version,
        created_by=created_by,
    )
    store.upsert_definition(draft)
    if activate_after:
        return activate(store, org_id=org_id, metric_id=metric_id, version=new_version)
    return draft
