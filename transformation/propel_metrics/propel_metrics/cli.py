"""CLI: propel-metrics validate | compile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from propel_metrics.codegen import check_drift, compile_metrics
from propel_metrics.validate import validate


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="propel-metrics")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="Validate metric YAML configs")
    v.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files or directories (default: shipped propel.* configs)",
    )
    v.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    c = sub.add_parser("compile", help="Compile active metrics to dbt SQL")
    c.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional config paths (default: shipped configs)",
    )
    c.add_argument(
        "--check",
        action="store_true",
        help="Check generated SQL for drift without writing",
    )
    c.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override generated output directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = list(args.paths) if getattr(args, "paths", None) else None

    if args.command == "validate":
        result = validate(paths)
        for warn in result.warnings:
            print(warn.format(), file=sys.stderr)
        for err in result.errors:
            print(err.format(), file=sys.stderr)
        if result.errors or (args.strict and result.warnings):
            print(
                f"validate failed: {len(result.errors)} error(s), "
                f"{len(result.warnings)} warning(s)",
                file=sys.stderr,
            )
            return 1
        print(
            f"validate ok: {len(result.warnings)} warning(s)",
        )
        return 0

    if args.command == "compile":
        if args.check:
            messages = check_drift(paths)
            if messages:
                for msg in messages:
                    print(msg, file=sys.stderr)
                print(
                    "compile --check failed: generated SQL has drifted",
                    file=sys.stderr,
                )
                return 1
            print("compile --check ok: no drift")
            return 0

        written = compile_metrics(paths, output_dir=args.out)
        for path in written:
            print(f"wrote {path}")
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
