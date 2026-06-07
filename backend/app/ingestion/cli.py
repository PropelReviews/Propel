"""Ingestion CLI — the single execution entrypoint.

On-server cron invokes this hourly in V1; a future Dagster schedule would call
the same command (or import `orchestrator.run_all`) without other changes.

    python -m app.ingestion.cli run
    python -m app.ingestion.cli run --account-id <uuid>
    python -m app.ingestion.cli run --job github_sync
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid

from app.ingestion import orchestrator
from app.otel_logging import setup_logging, shutdown_logging


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.ingestion.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run ingestion for active connections")
    run.add_argument(
        "--account-id",
        type=uuid.UUID,
        default=None,
        help="Limit to a single connected_accounts id",
    )
    run.add_argument(
        "--job",
        dest="job_name",
        choices=[job.name for job in orchestrator.JOBS],
        default=None,
        help="Limit to a single Meltano job",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging_enabled = setup_logging()
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            asyncio.run(
                orchestrator.run_all(account_id=args.account_id, job_name=args.job_name)
            )
    finally:
        if logging_enabled:
            shutdown_logging()


if __name__ == "__main__":
    main()
