"""Git-native push/pull for metric definitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from propel_metrics.resolve.lifecycle import activate, archive, save_draft
from propel_metrics.resolve.semantic_diff import classify_doc_diff
from propel_metrics.store.protocol import (
    METRIC_SET_ID,
    SYSTEM_ORG,
    DefinitionStore,
    StoredDefinition,
)

LOCKFILE_NAME = ".propel-lock.json"


@dataclass
class LockEntry:
    version: int
    revision: int
    content_hash: str | None


@dataclass
class PushResult:
    created: list[str]
    revised: list[str]
    drafted: list[str]
    activated: list[str]
    conflicts: list[str]
    unchanged: list[str]


def _slug_from_id(metric_id: str) -> str:
    if metric_id == METRIC_SET_ID:
        return "metric_set"
    return metric_id.split(".", 1)[-1]


def _namespace_from_id(metric_id: str, org_id: str) -> str:
    if metric_id == METRIC_SET_ID:
        return org_id
    return metric_id.split(".", 1)[0]


def _rel_path(org_id: str, row: StoredDefinition) -> Path:
    ns = _namespace_from_id(row.metric_id, org_id)
    return Path(ns) / f"{_slug_from_id(row.metric_id)}.yaml"


def read_lockfile(directory: Path) -> dict[str, LockEntry]:
    path = directory / LOCKFILE_NAME
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, LockEntry] = {}
    for mid, entry in (raw.get("metrics") or {}).items():
        out[mid] = LockEntry(
            version=int(entry["version"]),
            revision=int(entry.get("revision", 1)),
            content_hash=entry.get("content_hash"),
        )
    return out


def write_lockfile(
    directory: Path,
    *,
    org_id: str,
    rows: list[StoredDefinition],
) -> Path:
    payload = {
        "org_id": org_id,
        "metrics": {
            r.metric_id: {
                "version": r.version,
                "revision": r.revision,
                "content_hash": r.content_hash,
            }
            for r in sorted(rows, key=lambda x: x.metric_id)
        },
    }
    path = directory / LOCKFILE_NAME
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def pull(
    store: DefinitionStore,
    *,
    org_id: str,
    directory: Path,
    include_system: bool = True,
) -> list[Path]:
    """Export active definitions to ``directory`` and write a lockfile."""
    directory.mkdir(parents=True, exist_ok=True)
    rows: list[StoredDefinition] = []
    rows.extend(store.list_definitions(org_id, status="active"))
    if include_system and org_id != SYSTEM_ORG:
        rows.extend(store.list_definitions(SYSTEM_ORG, kind="Metric", status="active"))

    written: list[Path] = []
    for row in rows:
        rel = _rel_path(row.org_id if row.org_id != SYSTEM_ORG else "propel", row)
        # system metrics always under propel/
        if row.org_id == SYSTEM_ORG:
            rel = Path("propel") / f"{_slug_from_id(row.metric_id)}.yaml"
        elif row.metric_id == METRIC_SET_ID:
            rel = Path(org_id) / "metric_set.yaml"
        target = directory / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            row.yaml if row.yaml.endswith("\n") else row.yaml + "\n", encoding="utf-8"
        )
        written.append(target)

    write_lockfile(directory, org_id=org_id, rows=rows)
    return written


def _iter_yaml_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.rglob("*.yaml") if p.is_file())


def _target_org_for_doc(doc: dict[str, Any], org_id: str) -> tuple[str, str]:
    """Return (metric_id, target_org) for a document being pushed."""
    kind = doc["kind"]
    if kind == "MetricSet":
        return METRIC_SET_ID, (doc.get("metadata") or {}).get("org") or org_id
    mid = doc["metadata"]["id"]
    if str(mid).startswith("propel."):
        return mid, SYSTEM_ORG
    return mid, org_id


def push(
    store: DefinitionStore,
    *,
    org_id: str,
    directory: Path,
    created_by: str = "cli",
    activate_flag: bool = False,
    atomic: bool = True,
) -> PushResult:
    """Push YAML files under ``directory`` using the lockfile for concurrency."""
    lock = read_lockfile(directory)
    lock_org = None
    lock_path = directory / LOCKFILE_NAME
    if lock_path.is_file():
        lock_org = json.loads(lock_path.read_text(encoding="utf-8")).get("org_id")

    result = PushResult([], [], [], [], [], [])
    pending: list[tuple[Path, dict[str, Any], str]] = []

    for path in _iter_yaml_files(directory):
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: root must be a mapping")
        kind = doc.get("kind")
        if kind not in {"Metric", "MetricSet", "DimensionMapping"}:
            continue
        mid, target_org = _target_org_for_doc(doc, org_id)
        if target_org not in {org_id, SYSTEM_ORG}:
            continue
        if lock_org and target_org == org_id and lock_org != org_id:
            raise ValueError(f"lockfile org_id {lock_org!r} != {org_id!r}")
        pending.append((path, doc, text))

    conflicts: list[str] = []
    for _path, doc, _text in pending:
        mid, target_org = _target_org_for_doc(doc, org_id)
        active = store.get_definition(target_org, mid, status="active")
        locked = lock.get(mid)
        if locked and active and locked.version != active.version:
            conflicts.append(mid)
            continue
        if (
            locked
            and active
            and locked.revision != active.revision
            and classify_doc_diff(active.doc, doc) != "none"
        ):
            conflicts.append(mid)

    if conflicts and atomic:
        result.conflicts = conflicts
        return result

    for _path, doc, text in pending:
        mid, target_org = _target_org_for_doc(doc, org_id)
        if mid in conflicts:
            result.conflicts.append(mid)
            continue

        active = store.get_definition(target_org, mid, status="active")
        locked = lock.get(mid)
        if locked is None and active is None:
            row = save_draft(
                store, org_id=target_org, yaml_text=text, created_by=created_by
            )
            result.created.append(mid)
            if activate_flag:
                activate(store, org_id=target_org, metric_id=mid, version=row.version)
                result.activated.append(mid)
            continue

        prev = active.doc if active else None
        diff = classify_doc_diff(prev, doc)
        if diff == "none":
            result.unchanged.append(mid)
            continue
        row = save_draft(
            store, org_id=target_org, yaml_text=text, created_by=created_by
        )
        if diff == "non_semantic":
            result.revised.append(mid)
        else:
            result.drafted.append(mid)
            if activate_flag:
                activate(store, org_id=target_org, metric_id=mid, version=row.version)
                result.activated.append(mid)

    rows = store.list_definitions(org_id, status="active")
    rows.extend(store.list_definitions(SYSTEM_ORG, kind="Metric", status="active"))
    write_lockfile(directory, org_id=org_id, rows=rows)
    return result


# Re-export archive for CLI convenience
__all__ = [
    "LOCKFILE_NAME",
    "PushResult",
    "archive",
    "pull",
    "push",
    "read_lockfile",
    "write_lockfile",
]
