"""Compile inventory, determinism, and CLI CI gates."""

from __future__ import annotations

import hashlib
from pathlib import Path

from propel_metrics.cli import main
from propel_metrics.codegen import check_drift, check_inventory, compile_metrics
from propel_metrics.codegen.filters import compile_filter, compile_filters
from propel_metrics.codegen.sql import is_compilable, metric_model_filename
from propel_metrics.paths import GENERATED_DIR, PROPEL_CONFIGS_DIR
from propel_metrics.resolve import resolve_metrics


def test_shipped_config_inventory() -> None:
    yaml_files = sorted(PROPEL_CONFIGS_DIR.glob("*.yaml"))
    assert len(yaml_files) >= 7
    for path in yaml_files:
        text = path.read_text(encoding="utf-8")
        assert "apiVersion: propel/v1" in text
        assert "kind: Metric" in text


def test_compile_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    compile_metrics(output_dir=a)
    compile_metrics(output_dir=b)
    files_a = sorted(p.name for p in a.iterdir())
    files_b = sorted(p.name for p in b.iterdir())
    assert files_a == files_b
    for name in files_a:
        ha = hashlib.sha256((a / name).read_bytes()).hexdigest()
        hb = hashlib.sha256((b / name).read_bytes()).hexdigest()
        assert ha == hb, f"nondeterministic output for {name}"


def test_committed_generated_matches_compile() -> None:
    messages = check_drift()
    assert not messages, "\n".join(messages)


def test_inventory_complete() -> None:
    messages = check_inventory()
    assert not messages, "\n".join(messages)


def test_every_compilable_metric_file_exists() -> None:
    for metric in resolve_metrics(active_only=True):
        if not is_compilable(metric):
            continue
        path = GENERATED_DIR / metric_model_filename(metric.metric_id)
        assert path.is_file(), f"missing {path.name} for {metric.metric_id}"


def test_cli_ci_exits_zero() -> None:
    assert main(["ci"]) == 0


def test_cli_validate_strict_exits_zero() -> None:
    assert main(["validate", "--strict"]) == 0


def test_cli_compile_check_exits_zero() -> None:
    assert main(["compile", "--check"]) == 0


def test_filter_sql_compilation() -> None:
    sql = compile_filters(
        [
            {"field": "is_draft", "op": "eq", "value": False},
            {"field": "repo", "op": "starts_with", "value": "acme/"},
            {"not": {"field": "state", "op": "in", "value": ["open", "closed"]}},
        ]
    )
    assert sql is not None
    assert "is_draft = false" in sql
    assert "like 'acme/' || '%'" in sql
    assert "not (" in sql


def test_filter_sql_rejects_unsafe_identifier() -> None:
    try:
        compile_filter({"field": "repo;drop", "op": "eq", "value": "x"})
    except ValueError as exc:
        assert "unsafe" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for unsafe identifier")
