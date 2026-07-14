"""Three-pass metric config validation: structural → semantic → graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from propel_metrics.paths import CATALOG_PATH
from propel_metrics.validate.errors import ValidationResult
from propel_metrics.validate.graph import validate_graph
from propel_metrics.validate.loader import load_catalog, load_documents
from propel_metrics.validate.semantic import validate_files_semantic
from propel_metrics.validate.structural import (
    validate_catalog_structure,
    validate_files_structural,
)


def validate(
    paths: list[Path] | None = None,
    *,
    catalog_path: Path | None = None,
) -> ValidationResult:
    result = ValidationResult()
    catalog = load_catalog(catalog_path)
    result.extend(
        validate_catalog_structure(catalog, file=str(catalog_path or CATALOG_PATH))
    )
    if not result.ok:
        return result

    docs = load_documents(paths)
    if not docs:
        result.error(
            "E_NO_DOCS",
            "$",
            "no metric YAML documents found",
        )
        return result

    result.extend(validate_files_structural(docs))
    # Continue semantic/graph even with schema errors so authors see more at once,
    # but skip docs that failed structure for semantic to avoid noise.
    good_docs: list[tuple[Path, dict[str, Any]]] = []
    errored_files = {e.file for e in result.errors if e.file}
    for path, doc in docs:
        if str(path) in errored_files:
            continue
        good_docs.append((path, doc))

    result.extend(validate_files_semantic(good_docs, catalog))
    result.extend(validate_graph(docs))
    return result
