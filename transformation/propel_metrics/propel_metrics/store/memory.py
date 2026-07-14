"""In-memory DefinitionStore for unit tests."""

from __future__ import annotations

import copy
import uuid
from typing import Any

import yaml

from propel_metrics.store.protocol import (
    METRIC_SET_ID,
    SYSTEM_ORG,
    DefinitionNotice,
    DefinitionStore,
    EnrollmentRow,
    Kind,
    Status,
    StoredDefinition,
)


def _key(org_id: str, metric_id: str, version: int) -> tuple[str, str, int]:
    return (org_id, metric_id, version)


def _row_id(doc: dict[str, Any]) -> str:
    if doc.get("kind") == "MetricSet":
        return METRIC_SET_ID
    meta = doc.get("metadata") or {}
    return str(meta.get("id") or "unknown")


class MemoryDefinitionStore:
    """Dict-backed store implementing DefinitionStore."""

    def __init__(self) -> None:
        self._defs: dict[tuple[str, str, int], StoredDefinition] = {}
        self._enrollments: dict[str, dict[str, EnrollmentRow]] = {}
        self._notices: list[DefinitionNotice] = []
        self._dirty: dict[str, str] = {}

    def get_definition(
        self,
        org_id: str,
        metric_id: str,
        *,
        version: int | None = None,
        status: Status | None = None,
    ) -> StoredDefinition | None:
        if version is not None:
            row = self._defs.get(_key(org_id, metric_id, version))
            if row is None:
                return None
            if status is not None and row.status != status:
                return None
            return copy.deepcopy(row)

        candidates = [
            r for (o, m, _), r in self._defs.items() if o == org_id and m == metric_id
        ]
        if status is not None:
            candidates = [r for r in candidates if r.status == status]
        else:
            active = [r for r in candidates if r.status == "active"]
            if active:
                return copy.deepcopy(max(active, key=lambda r: r.version))
            broken = [r for r in candidates if r.status == "broken"]
            if broken:
                return copy.deepcopy(max(broken, key=lambda r: r.version))
        if not candidates:
            return None
        return copy.deepcopy(max(candidates, key=lambda r: r.version))

    def list_definitions(
        self,
        org_id: str,
        *,
        kind: Kind | None = None,
        status: Status | None = None,
    ) -> list[StoredDefinition]:
        rows = [r for (o, _, _), r in self._defs.items() if o == org_id]
        if kind is not None:
            rows = [r for r in rows if r.kind == kind]
        if status is not None:
            rows = [r for r in rows if r.status == status]
        rows.sort(key=lambda r: (r.metric_id, r.version))
        return [copy.deepcopy(r) for r in rows]

    def list_active_system_metrics(self) -> list[StoredDefinition]:
        return self.list_definitions(SYSTEM_ORG, kind="Metric", status="active")

    def upsert_definition(self, row: StoredDefinition) -> StoredDefinition:
        stored = copy.deepcopy(row)
        self._defs[_key(row.org_id, row.metric_id, row.version)] = stored
        return copy.deepcopy(stored)

    def set_status(
        self,
        org_id: str,
        metric_id: str,
        version: int,
        status: Status,
    ) -> None:
        row = self._defs.get(_key(org_id, metric_id, version))
        if row is None:
            raise KeyError(f"missing definition {org_id}/{metric_id}@{version}")
        row.status = status

    def replace_enrollments(self, org_id: str, rows: list[EnrollmentRow]) -> None:
        self._enrollments[org_id] = {r.metric_id: copy.deepcopy(r) for r in rows}

    def list_enrollments(self, org_id: str) -> list[EnrollmentRow]:
        return [copy.deepcopy(r) for r in self._enrollments.get(org_id, {}).values()]

    def add_notice(self, notice: DefinitionNotice) -> DefinitionNotice:
        stored = copy.deepcopy(notice)
        if stored.id is None:
            stored.id = str(uuid.uuid4())
        self._notices.append(stored)
        return copy.deepcopy(stored)

    def list_notices(
        self, org_id: str, metric_id: str | None = None
    ) -> list[DefinitionNotice]:
        rows = [n for n in self._notices if n.org_id == org_id]
        if metric_id is not None:
            rows = [n for n in rows if n.metric_id == metric_id]
        return [copy.deepcopy(n) for n in rows]

    def mark_dirty(self, content_hash: str, reason: str) -> None:
        self._dirty[content_hash] = reason

    def list_dirty(self) -> list[tuple[str, str]]:
        return list(self._dirty.items())

    def clear_dirty(self, content_hashes: list[str]) -> None:
        for h in content_hashes:
            self._dirty.pop(h, None)

    def put_metric_doc(
        self,
        org_id: str,
        doc: dict[str, Any],
        *,
        yaml_text: str | None = None,
        status: Status | None = None,
        version: int | None = None,
        parent_pin: dict[str, Any] | None = None,
        content_hash: str | None = None,
        resolved_json: dict[str, Any] | None = None,
        created_by: str = "test",
    ) -> StoredDefinition:
        meta = doc.get("metadata") or {}
        mid = _row_id(doc)
        ver = version if version is not None else int(meta.get("version", 1))
        st: Status = status or meta.get("status") or "draft"  # type: ignore[assignment]
        text = (
            yaml_text if yaml_text is not None else yaml.safe_dump(doc, sort_keys=False)
        )
        row = StoredDefinition(
            org_id=org_id,
            metric_id=mid,
            version=ver,
            revision=1,
            kind=doc["kind"],
            yaml=text,
            doc=copy.deepcopy(doc),
            status=st,
            parent_pin=parent_pin,
            content_hash=content_hash,
            resolved_json=resolved_json,
            created_by=created_by,
        )
        return self.upsert_definition(row)


# Structural check that the memory store matches the protocol surface.
_: type[DefinitionStore] = MemoryDefinitionStore  # type: ignore[assignment]
