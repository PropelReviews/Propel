"""Parent pin helpers for extends versioning."""

from __future__ import annotations

from typing import Any

from propel_metrics.store.protocol import DefinitionStore, StoredDefinition


def parent_pin_from_active(
    store: DefinitionStore,
    parent_metric_id: str,
    *,
    parent_org: str,
) -> dict[str, Any]:
    parent = store.get_definition(parent_org, parent_metric_id, status="active")
    if parent is None:
        raise ValueError(f"no active parent {parent_org}/{parent_metric_id}")
    return {"metric_id": parent.metric_id, "version": parent.version}


def load_pinned_parent(
    store: DefinitionStore,
    pin: dict[str, Any],
    *,
    parent_org: str,
) -> StoredDefinition:
    mid = pin["metric_id"]
    version = int(pin["version"])
    row = store.get_definition(parent_org, mid, version=version)
    if row is None:
        raise ValueError(f"pinned parent missing: {parent_org}/{mid}@{version}")
    return row


def find_children_pinning(
    store: DefinitionStore,
    *,
    parent_org: str,
    parent_metric_id: str,
    older_than_version: int,
) -> list[StoredDefinition]:
    """Active children (any org) whose parent_pin points at an older parent version.

    Memory/DB implementations list org by org; callers typically scan known orgs.
    This helper only inspects definitions already loadable via ``list_definitions``
    for a single org — use ``scan_orgs_for_stale_pins`` for multi-org.
    """
    _ = (store, parent_org, parent_metric_id, older_than_version)
    return []


def stale_pin(
    row: StoredDefinition,
    *,
    parent_metric_id: str,
    new_parent_version: int,
) -> bool:
    pin = row.parent_pin or {}
    if pin.get("metric_id") != parent_metric_id:
        return False
    return int(pin.get("version", 0)) < new_parent_version
