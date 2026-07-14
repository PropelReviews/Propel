"""Filesystem locations for schemas, catalog, configs, and codegen output."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_TRANSFORMATION = PACKAGE_ROOT.parent.parent  # transformation/
REPO_ROOT = REPO_TRANSFORMATION.parent

SCHEMA_DIR = PACKAGE_ROOT / "schema"
CATALOG_PATH = PACKAGE_ROOT / "catalog" / "entities.yaml"
CONFIGS_DIR = PACKAGE_ROOT / "configs"
PROPEL_CONFIGS_DIR = CONFIGS_DIR / "propel"

DBT_PROJECT_DIR = REPO_TRANSFORMATION / "dbt"
GENERATED_DIR = DBT_PROJECT_DIR / "models" / "metrics" / "generated"
