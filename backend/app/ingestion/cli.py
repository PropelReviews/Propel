"""Ingestion CLI — the single execution entrypoint.

The Dagster schedule drives ingestion in deployed environments by importing
`orchestrator.run_all`; this CLI runs the same code path for local/manual runs.

    python -m app.ingestion.cli run
    python -m app.ingestion.cli run --account-id <uuid>
    python -m app.ingestion.cli run --job github_commits_sync
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from datetime import date

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
    run.add_argument(
        "--start-date",
        dest="start_date",
        type=lambda raw: date.fromisoformat(raw).isoformat(),
        default=None,
        help="Backfill: override the watermark and re-pull since this ISO date",
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
                orchestrator.run_all(
                    account_id=args.account_id,
                    job_name=args.job_name,
                    start_date=args.start_date,
                )
            )
    finally:
        if logging_enabled:
            shutdown_logging()


if __name__ == "__main__":
    main()
