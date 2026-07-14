"""Load YAML metric documents and the entity catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from propel_metrics.paths import CATALOG_PATH, PROPEL_CONFIGS_DIR


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or CATALOG_PATH)


def discover_config_files(paths: list[Path] | None = None) -> list[Path]:
    """Return Metric/MetricSet/DimensionMapping YAML files to validate."""
    if paths:
        files: list[Path] = []
        for p in paths:
            if p.is_file():
                files.append(p)
            elif p.is_dir():
                files.extend(sorted(p.rglob("*.yaml")))
                files.extend(sorted(p.rglob("*.yml")))
        return sorted({f.resolve() for f in files})
    return sorted(PROPEL_CONFIGS_DIR.rglob("*.yaml"))


def load_documents(
    paths: list[Path] | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    docs: list[tuple[Path, dict[str, Any]]] = []
    for path in discover_config_files(paths):
        data = load_yaml(path)
        if data is None:
            continue
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a YAML mapping at document root")
        docs.append((path, data))
    return docs
