"""Unit test for fct_metric_values swap SQL semantics (no live warehouse needed)."""

from __future__ import annotations

from pathlib import Path

MACRO = (
    Path(__file__).resolve().parents[2]
    / "transformation"
    / "dbt"
    / "macros"
    / "swap_metric_values.sql"
)


def test_swap_macro_is_transactional_delete_insert() -> None:
    text = MACRO.read_text(encoding="utf-8")
    assert "begin;" in text.lower() or "begin;" in text
    assert "delete from" in text.lower()
    assert "insert into" in text.lower()
    assert "commit;" in text.lower() or "commit;" in text
    assert "metric_id" in text
    assert "definition_version" in text
    # Shared vs per-org scoping
    assert "tenant_ids" in text
    assert "dim_team" in text
    assert "is_total" in text
