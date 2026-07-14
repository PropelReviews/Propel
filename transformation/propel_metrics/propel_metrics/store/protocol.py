"""Definition store protocol for org resolve / push-pull / activation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Kind = Literal["Metric", "MetricSet", "DimensionMapping"]
Status = Literal["draft", "active", "deprecated", "archived", "broken"]

SYSTEM_ORG = "__system"
METRIC_SET_ID = "metric_set"


@dataclass
class StoredDefinition:
    org_id: str
    metric_id: str
    version: int
    revision: int
    kind: Kind
    yaml: str
    doc: dict[str, Any]
    resolved_json: dict[str, Any] | None = None
    content_hash: str | None = None
    status: Status = "draft"
    parent_pin: dict[str, Any] | None = None
    catalog_version: str = "1"
    created_by: str = "system"


@dataclass
class EnrollmentRow:
    org_id: str
    metric_id: str
    definition_org: str
    definition_version: int
    params_json: dict[str, Any] | None = None
    content_hash: str | None = None


@dataclass
class DefinitionNotice:
    org_id: str
    metric_id: str
    notice: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


class DefinitionStore(Protocol):
    def get_definition(
        self,
        org_id: str,
        metric_id: str,
        *,
        version: int | None = None,
        status: Status | None = None,
    ) -> StoredDefinition | None:
        """Return a definition. If version is None, prefer active then broken."""
        ...

    def list_definitions(
        self,
        org_id: str,
        *,
        kind: Kind | None = None,
        status: Status | None = None,
    ) -> list[StoredDefinition]: ...

    def list_active_system_metrics(self) -> list[StoredDefinition]: ...

    def upsert_definition(self, row: StoredDefinition) -> StoredDefinition: ...

    def set_status(
        self,
        org_id: str,
        metric_id: str,
        version: int,
        status: Status,
    ) -> None: ...

    def replace_enrollments(self, org_id: str, rows: list[EnrollmentRow]) -> None: ...

    def list_enrollments(self, org_id: str) -> list[EnrollmentRow]: ...

    def add_notice(self, notice: DefinitionNotice) -> DefinitionNotice: ...

    def list_notices(
        self, org_id: str, metric_id: str | None = None
    ) -> list[DefinitionNotice]: ...

    def mark_dirty(self, content_hash: str, reason: str) -> None: ...

    def list_dirty(self) -> list[tuple[str, str]]: ...

    def clear_dirty(self, content_hashes: list[str]) -> None: ...
