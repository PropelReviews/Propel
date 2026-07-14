"""CLI: propel-metrics validate | compile | ci | import-system | pull | push | ..."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from propel_metrics.codegen import check_drift, check_inventory, compile_metrics
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
        help="Check generated SQL for drift + inventory without writing",
    )
    c.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override generated output directory",
    )

    ci = sub.add_parser(
        "ci",
        help="Run CI gates: validate --strict, compile --check, inventory",
    )
    ci.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional config paths (default: shipped configs)",
    )

    imp = sub.add_parser(
        "import-system",
        help="Import shipped propel.* YAMLs into a definition store",
    )
    imp.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROPEL_METRICS_STORE", ".propel-store.json")),
        help="JSON store path (default: .propel-store.json or $PROPEL_METRICS_STORE)",
    )

    pull = sub.add_parser("pull", help="Export active definitions to a directory")
    pull.add_argument("--org", required=True, help="Org slug (MetricSet metadata.org)")
    pull.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("metrics-out"),
        help="Output directory",
    )
    pull.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROPEL_METRICS_STORE", ".propel-store.json")),
    )

    push = sub.add_parser("push", help="Push YAML definitions into the store")
    push.add_argument("--org", required=True, help="Org slug")
    push.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("metrics-out"),
    )
    push.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROPEL_METRICS_STORE", ".propel-store.json")),
    )
    push.add_argument(
        "--activate",
        action="store_true",
        help="Activate semantic drafts after push",
    )
    push.add_argument(
        "--no-atomic",
        action="store_true",
        help="Continue past conflicts (default is all-or-nothing)",
    )

    repin = sub.add_parser("repin", help="Repin an extends child to the active parent")
    repin.add_argument("--org", required=True)
    repin.add_argument("--id", required=True, dest="metric_id")
    repin.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROPEL_METRICS_STORE", ".propel-store.json")),
    )
    repin.add_argument("--activate", action="store_true", default=True)

    arch = sub.add_parser("archive", help="Archive an active definition")
    arch.add_argument("--org", required=True)
    arch.add_argument("--id", required=True, dest="metric_id")
    arch.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("PROPEL_METRICS_STORE", ".propel-store.json")),
    )

    return parser


def _open_store(path: Path):
    from propel_metrics.store.jsonfile import JsonFileDefinitionStore

    return JsonFileDefinitionStore(path)


def _cmd_validate(paths: list[Path] | None, *, strict: bool) -> int:
    result = validate(paths)
    for warn in result.warnings:
        print(warn.format(), file=sys.stderr)
    for err in result.errors:
        print(err.format(), file=sys.stderr)
    if result.errors or (strict and result.warnings):
        print(
            f"validate failed: {len(result.errors)} error(s), "
            f"{len(result.warnings)} warning(s)",
            file=sys.stderr,
        )
        return 1
    print(f"validate ok: {len(result.warnings)} warning(s)")
    return 0


def _cmd_compile(
    paths: list[Path] | None,
    *,
    check: bool,
    out: Path | None,
) -> int:
    if check:
        messages = check_drift(paths)
        if messages:
            for msg in messages:
                print(msg, file=sys.stderr)
            print(
                "compile --check failed: generated SQL has drifted "
                "or inventory is incomplete",
                file=sys.stderr,
            )
            return 1
        print("compile --check ok: no drift, inventory complete")
        return 0

    written = compile_metrics(paths, output_dir=out)
    for path in written:
        print(f"wrote {path}")
    return 0


def _cmd_ci(paths: list[Path] | None) -> int:
    print("==> propel-metrics validate --strict")
    if _cmd_validate(paths, strict=True) != 0:
        return 1
    print("==> propel-metrics compile --check")
    if _cmd_compile(paths, check=True, out=None) != 0:
        return 1
    print("==> inventory summary")
    inv = check_inventory(paths)
    if inv:
        for msg in inv:
            print(msg, file=sys.stderr)
        return 1
    print("ci ok")
    return 0


def _cmd_import_system(store_path: Path) -> int:
    from propel_metrics.store.import_system import import_system_metrics

    store = _open_store(store_path)
    written = import_system_metrics(store)
    print(f"imported {len(written)} system metric(s) into {store_path}")
    return 0


def _cmd_pull(store_path: Path, org: str, directory: Path) -> int:
    from propel_metrics.sync.pushpull import pull

    store = _open_store(store_path)
    written = pull(store, org_id=org, directory=directory)
    print(f"pulled {len(written)} file(s) to {directory}")
    return 0


def _cmd_push(
    store_path: Path,
    org: str,
    directory: Path,
    *,
    activate_flag: bool,
    atomic: bool,
) -> int:
    from propel_metrics.sync.pushpull import push

    store = _open_store(store_path)
    result = push(
        store,
        org_id=org,
        directory=directory,
        activate_flag=activate_flag,
        atomic=atomic,
    )
    if result.conflicts:
        print(
            "push conflicts (re-pull and re-apply): " + ", ".join(result.conflicts),
            file=sys.stderr,
        )
        return 1
    print(
        "push ok: "
        f"created={result.created} revised={result.revised} "
        f"drafted={result.drafted} activated={result.activated} "
        f"unchanged={result.unchanged}"
    )
    return 0


def _cmd_repin(
    store_path: Path, org: str, metric_id: str, *, activate_flag: bool
) -> int:
    from propel_metrics.resolve.lifecycle import repin

    store = _open_store(store_path)
    row = repin(
        store,
        org_id=org,
        metric_id=metric_id,
        activate_after=activate_flag,
    )
    print(f"repinned {org}/{metric_id} -> v{row.version} pin={row.parent_pin}")
    return 0


def _cmd_archive(store_path: Path, org: str, metric_id: str) -> int:
    from propel_metrics.resolve.lifecycle import archive

    store = _open_store(store_path)
    row = archive(store, org_id=org, metric_id=metric_id)
    print(f"archived {org}/{metric_id}@{row.version}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = list(args.paths) if getattr(args, "paths", None) else None

    if args.command == "validate":
        return _cmd_validate(paths, strict=args.strict)
    if args.command == "compile":
        return _cmd_compile(paths, check=args.check, out=args.out)
    if args.command == "ci":
        return _cmd_ci(paths)
    if args.command == "import-system":
        return _cmd_import_system(args.store)
    if args.command == "pull":
        return _cmd_pull(args.store, args.org, args.directory)
    if args.command == "push":
        return _cmd_push(
            args.store,
            args.org,
            args.directory,
            activate_flag=args.activate,
            atomic=not args.no_atomic,
        )
    if args.command == "repin":
        return _cmd_repin(
            args.store, args.org, args.metric_id, activate_flag=args.activate
        )
    if args.command == "archive":
        return _cmd_archive(args.store, args.org, args.metric_id)

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
