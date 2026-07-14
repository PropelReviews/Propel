"""Each tests/fixtures/invalid/*.yaml must fail validation with its expected code."""

from __future__ import annotations

import re
from pathlib import Path

from propel_metrics.validate import validate

INVALID_DIR = Path(__file__).parent / "fixtures" / "invalid"
_EXPECT_RE = re.compile(r"^#\s*expect:\s*(\S+)")


def _expected_code(path: Path) -> str | None:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    match = _EXPECT_RE.match(first)
    if not match:
        return None
    code = match.group(1)
    if code.startswith("("):
        return None  # companion / parent file
    return code


def _groups() -> list[tuple[str, list[Path]]]:
    """Group invalid fixtures: standalone files, or child+parent companions."""
    files = sorted(INVALID_DIR.glob("*.yaml"))
    used: set[Path] = set()
    groups: list[tuple[str, list[Path]]] = []

    # Pair visibility_escalation with its parent explicitly
    child = INVALID_DIR / "visibility_escalation.yaml"
    parent = INVALID_DIR / "visibility_escalation_parent.yaml"
    if child.exists() and parent.exists():
        code = _expected_code(child)
        assert code is not None
        groups.append((code, [child, parent]))
        used.update({child, parent})

    for path in files:
        if path in used:
            continue
        code = _expected_code(path)
        if code is None:
            continue
        groups.append((code, [path]))
    return groups


def test_invalid_fixture_directory_nonempty() -> None:
    assert _groups(), "expected invalid fixtures under tests/fixtures/invalid/"


def test_invalid_fixtures_fail_with_expected_codes() -> None:
    failures: list[str] = []
    for code, paths in _groups():
        result = validate(paths)
        codes = {e.code for e in result.errors}
        if result.ok:
            failures.append(
                f"{[p.name for p in paths]}: expected failure {code}, got ok"
            )
        elif code not in codes:
            failures.append(
                f"{[p.name for p in paths]}: expected {code}, got {sorted(codes)}"
            )
    assert not failures, "\n".join(failures)
