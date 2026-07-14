"""Seed a DefinitionStore from shipped propel.* YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.ir.hashutil import plan_content_hash, plan_to_canonical_dict
from propel_metrics.ir.types import CompiledPlan
from propel_metrics.paths import PROPEL_CONFIGS_DIR
from propel_metrics.resolve import resolve_metrics
from propel_metrics.store.protocol import SYSTEM_ORG, DefinitionStore, StoredDefinition
from propel_metrics.validate.loader import load_catalog, load_documents


def import_system_metrics(
    store: DefinitionStore,
    *,
    paths: list[Path] | None = None,
    created_by: str = "system",
) -> list[StoredDefinition]:
    """Import Metric YAMLs under configs/propel into ``__system``.

    Computes resolved_json + content_hash for active compilable metrics.
    Idempotent upsert by (org, id, version).
    """
    config_paths = paths or [PROPEL_CONFIGS_DIR]
    catalog = load_catalog()
    catalog_version = str(catalog.get("catalogVersion", "1"))
    docs = load_documents(config_paths)
    file_resolved = {
        m.metric_id: m for m in resolve_metrics(config_paths, active_only=False)
    }
    by_all = {m.metric_id: m for m in resolve_metrics(config_paths, active_only=False)}

    written: list[StoredDefinition] = []
    for path, doc in docs:
        if doc.get("kind") != "Metric":
            continue
        meta = doc.get("metadata") or {}
        mid = meta["id"]
        version = int(meta.get("version", 1))
        status = meta.get("status", "draft")
        yaml_text = path.read_text(encoding="utf-8")

        resolved_json = None
        digest = None
        parent_pin = None
        extends = (doc.get("spec") or {}).get("extends")
        if extends and mid in file_resolved:
            parent = file_resolved.get(extends)
            if parent is not None:
                parent_pin = {
                    "metric_id": extends,
                    "version": parent.version,
                }

        if status in {"active", "deprecated"} and mid in by_all:
            metric = by_all[mid]
            try:
                plan = build_compiled_plan(metric, by_all)
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
                resolved_json = plan_to_canonical_dict(plan)
                digest = plan_content_hash(plan)
            except ValueError:
                resolved_json = None
                digest = None

        row = StoredDefinition(
            org_id=SYSTEM_ORG,
            metric_id=mid,
            version=version,
            revision=1,
            kind="Metric",
            yaml=yaml_text,
            doc=doc,
            resolved_json=resolved_json,
            content_hash=digest,
            status=status,  # type: ignore[arg-type]
            parent_pin=parent_pin,
            catalog_version=catalog_version,
            created_by=created_by,
        )
        written.append(store.upsert_definition(row))
    return written


def doc_from_yaml_text(text: str) -> dict[str, Any]:
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("YAML root must be a mapping")
    return loaded
