"""JSON-file backed DefinitionStore for local CLI / dogfood."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import (
    DefinitionNotice,
    EnrollmentRow,
    StoredDefinition,
)


def _row_to_dict(row: StoredDefinition) -> dict[str, Any]:
    return {
        "org_id": row.org_id,
        "metric_id": row.metric_id,
        "version": row.version,
        "revision": row.revision,
        "kind": row.kind,
        "yaml": row.yaml,
        "doc": row.doc,
        "resolved_json": row.resolved_json,
        "content_hash": row.content_hash,
        "status": row.status,
        "parent_pin": row.parent_pin,
        "catalog_version": row.catalog_version,
        "created_by": row.created_by,
    }


def _row_from_dict(data: dict[str, Any]) -> StoredDefinition:
    return StoredDefinition(
        org_id=data["org_id"],
        metric_id=data["metric_id"],
        version=int(data["version"]),
        revision=int(data.get("revision", 1)),
        kind=data["kind"],
        yaml=data["yaml"],
        doc=data["doc"],
        resolved_json=data.get("resolved_json"),
        content_hash=data.get("content_hash"),
        status=data.get("status", "draft"),
        parent_pin=data.get("parent_pin"),
        catalog_version=data.get("catalog_version", "1"),
        created_by=data.get("created_by", "system"),
    )


class JsonFileDefinitionStore(MemoryDefinitionStore):
    """Memory store that persists to a JSON file on every mutation."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        if path.is_file():
            self._load()

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for item in raw.get("definitions", []):
            row = _row_from_dict(item)
            self._defs[(row.org_id, row.metric_id, row.version)] = row
        for org_id, rows in (raw.get("enrollments") or {}).items():
            self._enrollments[org_id] = {
                r["metric_id"]: EnrollmentRow(
                    org_id=r["org_id"],
                    metric_id=r["metric_id"],
                    definition_org=r["definition_org"],
                    definition_version=int(r["definition_version"]),
                    params_json=r.get("params_json"),
                    content_hash=r.get("content_hash"),
                )
                for r in rows
            }
        for n in raw.get("notices", []):
            self._notices.append(
                DefinitionNotice(
                    id=n.get("id"),
                    org_id=n["org_id"],
                    metric_id=n["metric_id"],
                    notice=n["notice"],
                    payload=n.get("payload") or {},
                )
            )
        self._dirty = dict(raw.get("dirty") or {})

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "definitions": [_row_to_dict(r) for r in self._defs.values()],
            "enrollments": {
                org: [
                    {
                        "org_id": r.org_id,
                        "metric_id": r.metric_id,
                        "definition_org": r.definition_org,
                        "definition_version": r.definition_version,
                        "params_json": r.params_json,
                        "content_hash": r.content_hash,
                    }
                    for r in rows.values()
                ]
                for org, rows in self._enrollments.items()
            },
            "notices": [
                {
                    "id": n.id,
                    "org_id": n.org_id,
                    "metric_id": n.metric_id,
                    "notice": n.notice,
                    "payload": n.payload,
                }
                for n in self._notices
            ],
            "dirty": self._dirty,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def upsert_definition(self, row: StoredDefinition) -> StoredDefinition:
        out = super().upsert_definition(row)
        self._save()
        return out

    def set_status(self, org_id: str, metric_id: str, version: int, status) -> None:  # type: ignore[override]
        super().set_status(org_id, metric_id, version, status)
        self._save()

    def replace_enrollments(self, org_id: str, rows: list[EnrollmentRow]) -> None:
        super().replace_enrollments(org_id, rows)
        self._save()

    def add_notice(self, notice: DefinitionNotice) -> DefinitionNotice:
        out = super().add_notice(notice)
        self._save()
        return out

    def mark_dirty(self, content_hash: str, reason: str) -> None:
        super().mark_dirty(content_hash, reason)
        self._save()

    def clear_dirty(self, content_hashes: list[str]) -> None:
        super().clear_dirty(content_hashes)
        self._save()
