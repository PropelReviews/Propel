"""Corpus parity: Python formula parser vs shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from propel_metrics.expr.json_ast import try_parse_json

CORPUS = Path(__file__).parent / "fixtures" / "formula_corpus.json"


def test_formula_corpus_python_ok_flags():
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))
    for case in cases:
        result = try_parse_json(case["expr"])
        assert result["ok"] is case["ok"], case
