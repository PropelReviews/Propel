"""JSON Schema structural validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaError

from propel_metrics.paths import SCHEMA_DIR
from propel_metrics.validate.errors import ValidationResult

_KIND_SCHEMA = {
    "Metric": "metric.schema.json",
    "MetricSet": "metric_set.schema.json",
    "DimensionMapping": "dimension_mapping.schema.json",
}


def _load_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _json_path(error: JsonSchemaError) -> str:
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            if parts:
                parts.append(f".{part}")
            else:
                parts.append(str(part))
    return "".join(parts) or "$"


def validate_document_structure(
    doc: dict[str, Any],
    *,
    file: str | None = None,
) -> ValidationResult:
    result = ValidationResult()
    kind = doc.get("kind")
    if kind not in _KIND_SCHEMA:
        result.error(
            "E_UNKNOWN_KIND",
            "kind",
            f"unknown kind {kind!r}; expected one of {sorted(_KIND_SCHEMA)}",
            file=file,
        )
        return result

    schema = _load_schema(_KIND_SCHEMA[kind])
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    for error in errors:
        result.error(
            "E_SCHEMA",
            _json_path(error),
            error.message,
            file=file,
        )
    return result


def validate_catalog_structure(
    catalog: dict[str, Any],
    *,
    file: str | None = None,
) -> ValidationResult:
    result = ValidationResult()
    schema = _load_schema("catalog.schema.json")
    validator = Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(catalog), key=lambda e: list(e.absolute_path)
    ):
        result.error(
            "E_SCHEMA",
            _json_path(error),
            error.message,
            file=file,
        )
    return result


def validate_files_structural(
    docs: list[tuple[Path, dict[str, Any]]],
) -> ValidationResult:
    result = ValidationResult()
    for path, doc in docs:
        result.extend(validate_document_structure(doc, file=str(path)))
    return result
