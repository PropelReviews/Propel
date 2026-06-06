"""Subprocess seam for running Meltano jobs.

Kept deliberately small so the orchestrator (and tests) can treat a Meltano run
as a single awaitable that returns an exit code and captured output. This is
also the boundary a future Dagster op would call.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("propel.ingestion")


def project_dir() -> Path:
    override = os.environ.get("MELTANO_PROJECT_DIR")
    if override:
        return Path(override)
    # backend/app/ingestion/meltano_runner.py -> backend/meltano
    return Path(__file__).resolve().parents[2] / "meltano"


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def run_job(
    job: str, env: dict[str, str], *, full_refresh: bool = True
) -> RunResult:
    """Run `meltano run <job>` with the given extra environment."""
    command = ["meltano", "run"]
    if full_refresh:
        # Drive incrementality from our own watermark (start_date) instead of
        # shared Meltano state; idempotent upserts dedupe any re-pulled rows.
        command.append("--full-refresh")
    command.append(job)

    merged_env = {**os.environ, **env}
    run_id = env.get("PROPEL_RUN_ID")
    extra = {
        "event": "extraction.meltano",
        "ingestion.job": job,
        "ingestion.run_id": run_id,
        "connected_account.id": env.get("PROPEL_CONNECTED_ACCOUNT_ID"),
        "tenant.id": env.get("PROPEL_TENANT_ID"),
    }
    logger.info("Meltano job starting", extra=extra)

    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(project_dir()),
        env=merged_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    result = RunResult(
        returncode=process.returncode or 0,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )
    outcome = {**extra, "process.returncode": result.returncode}
    if result.ok:
        # Tail stdout even on success: Singer/Meltano print extracted/loaded row
        # counts here, which is the quickest way to explain a 0-record run.
        outcome["process.stdout_tail"] = _tail(result.stdout)
        logger.info("Meltano job completed", extra=outcome)
    else:
        outcome["error.message"] = _tail(result.stderr or result.stdout)
        logger.error("Meltano job failed", extra=outcome)
    return result


def _tail(message: str, *, limit: int = 500) -> str:
    message = (message or "").strip()
    return message[-limit:]
