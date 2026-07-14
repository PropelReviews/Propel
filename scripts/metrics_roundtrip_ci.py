#!/usr/bin/env python3
"""CI bridge: propel.* YAML → UI emit-roundtrip normalize must be stable.

For each non-advanced shipped config:
  1. Skip if metadata.advanced or measure.type == sql / filter sql
  2. Run frontend/scripts/emit-roundtrip.mjs (must exit 0)
  3. Optionally compare content_hash of resolved specs via propel_metrics

Exit non-zero on any failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIGS = (
    REPO
    / "transformation"
    / "propel_metrics"
    / "propel_metrics"
    / "configs"
    / "propel"
)
EMIT = REPO / "frontend" / "scripts" / "emit-roundtrip.mjs"


def is_advanced(doc: dict) -> bool:
    meta = doc.get("metadata") or {}
    if meta.get("advanced"):
        return True
    measure = (doc.get("spec") or {}).get("measure") or {}
    if measure.get("type") == "sql" or "sql" in measure:
        return True
    return False


def main() -> int:
    import yaml

    files = sorted(CONFIGS.glob("*.yaml"))
    if not files:
        print("no configs found", file=sys.stderr)
        return 1
    failures = 0
    checked = 0
    for path in files:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or is_advanced(doc):
            print(f"skip advanced {path.name}")
            continue
        checked += 1
        proc = subprocess.run(
            ["node", str(EMIT), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(f"FAIL {path.name}: {proc.stderr.strip()}", file=sys.stderr)
            failures += 1
        else:
            # Ensure output is JSON
            try:
                json.loads(proc.stdout)
            except json.JSONDecodeError:
                print(f"FAIL {path.name}: non-json stdout", file=sys.stderr)
                failures += 1
                continue
            print(f"ok {path.name}")
    print(f"checked={checked} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
