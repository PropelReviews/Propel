"""JSON Schema + catalog self-checks."""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator
from propel_metrics.paths import CATALOG_PATH, SCHEMA_DIR
from propel_metrics.validate.loader import load_catalog
from propel_metrics.validate.structural import validate_catalog_structure


def test_schema_files_are_valid_json_schema() -> None:
    meta = Draft202012Validator.META_SCHEMA
    validator = Draft202012Validator(meta)
    schemas = sorted(SCHEMA_DIR.glob("*.schema.json"))
    assert schemas, "expected schema files"
    for path in schemas:
        schema = json.loads(path.read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(schema), key=lambda e: e.path)
        assert not errors, f"{path.name}: " + "; ".join(e.message for e in errors)


def test_catalog_validates_against_schema() -> None:
    catalog = load_catalog()
    result = validate_catalog_structure(catalog, file=str(CATALOG_PATH))
    assert result.ok, "\n".join(e.format() for e in result.errors)


def test_catalog_entities_have_dbt_model_and_tenant_key() -> None:
    catalog = load_catalog()
    for name, entity in catalog["entities"].items():
        assert entity.get("dbt_model"), f"{name} missing dbt_model"
        fields = entity["fields"]
        tenant_fields = [
            fname for fname, meta in fields.items() if meta.get("role") == "tenant_key"
        ]
        assert tenant_fields == ["tenant_id"], (
            f"{name} must have tenant_id as sole tenant_key, got {tenant_fields}"
        )
        keys = [fname for fname, meta in fields.items() if meta.get("role") == "key"]
        assert keys, f"{name} missing key field"


def test_schema_dir_matches_expected_kinds() -> None:
    names = {p.name for p in SCHEMA_DIR.glob("*.schema.json")}
    assert names >= {
        "metric.schema.json",
        "metric_set.schema.json",
        "dimension_mapping.schema.json",
        "catalog.schema.json",
    }
