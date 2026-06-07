"""Ingestion CLI — the single execution entrypoint.

Dagster ops and manual CLI runs call the same orchestrator.

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
from app.ingestion.logging_config import (
    configure_ingestion_logging,
    shutdown_ingestion_logging,
)

logger = logging.getLogger("propel.ingestion")


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
    otel_enabled = configure_ingestion_logging(service_name="propel-ingestion")
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "run":
            logger.info(
                "Ingestion CLI starting",
                extra={
                    "event": "extraction.cli",
                    "ingestion.account_id": str(args.account_id)
                    if args.account_id
                    else None,
                    "ingestion.job_filter": args.job_name,
                },
            )
            asyncio.run(
                orchestrator.run_all(account_id=args.account_id, job_name=args.job_name)
            )
            logger.info("Ingestion CLI finished", extra={"event": "extraction.cli"})
    finally:
        shutdown_ingestion_logging(otel_enabled)


if __name__ == "__main__":
    main()
