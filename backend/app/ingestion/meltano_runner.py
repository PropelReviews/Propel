"""Subprocess seam for running Meltano jobs.

Kept deliberately small so the orchestrator (and tests) can treat a Meltano run
as a single awaitable that returns an exit code and captured output. This is
also the boundary a future Dagster op would call.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
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
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


async def _read_stream(
    stream: asyncio.StreamReader | None,
    *,
    extra: dict[str, object],
    stream_name: str,
    lines: list[str],
) -> None:
    if stream is None:
        return
    while True:
        chunk = await stream.readline()
        if not chunk:
            break
        text = chunk.decode(errors="replace").rstrip()
        if not text:
            continue
        lines.append(text)
        level = logging.WARNING if stream_name == "stderr" else logging.INFO
        logger.log(
            level,
            "Meltano output",
            extra={
                **extra,
                "meltano.stream": stream_name,
                "meltano.line": text,
            },
        )


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
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    await asyncio.gather(
        _read_stream(
            process.stdout,
            extra=extra,
            stream_name="stdout",
            lines=stdout_lines,
        ),
        _read_stream(
            process.stderr,
            extra=extra,
            stream_name="stderr",
            lines=stderr_lines,
        ),
    )
    returncode = await process.wait()
    stdout = "\n".join(stdout_lines)
    stderr = "\n".join(stderr_lines)
    result = RunResult(
        returncode=returncode or 0,
        stdout=stdout,
        stderr=stderr,
        stdout_lines=stdout_lines,
        stderr_lines=stderr_lines,
    )
    outcome = {
        **extra,
        "process.returncode": result.returncode,
        "meltano.stdout_lines": len(stdout_lines),
        "meltano.stderr_lines": len(stderr_lines),
    }
    if result.ok:
        logger.info("Meltano job completed", extra=outcome)
    else:
        outcome["error.message"] = _tail(result.stderr or result.stdout)
        logger.error("Meltano job failed", extra=outcome)
    return result


def _tail(message: str, *, limit: int = 500) -> str:
    message = (message or "").strip()
    return message[-limit:]
