"""ECS run launcher that routes run workers through entrypoint.sh.

``EcsRunLauncher`` registers per-run task definitions with ``entryPoint: []`` and
sets the container command to ``dagster api execute_run ...``. That bypasses the
image ``ENTRYPOINT`` (``/entrypoint.sh``), so run workers never get the
orchestration venv on ``PATH``, ``PYTHONPATH``, or Dagster Postgres storage prep
— the ECS task starts but the worker never reports STARTED.

``PropelEcsRunLauncher`` prepends ``/entrypoint.sh`` so production run workers
follow the same bootstrap path as ``dagster-service``.
"""

from __future__ import annotations

from dagster._core.launcher.base import LaunchRunContext
from dagster._grpc.types import ExecuteRunArgs
from dagster_aws.ecs import EcsRunLauncher

_ENTRYPOINT = "/entrypoint.sh"


class PropelEcsRunLauncher(EcsRunLauncher):
    def _get_command_args(
        self, run_args: ExecuteRunArgs, context: LaunchRunContext
    ) -> list[str]:
        return [_ENTRYPOINT, *super()._get_command_args(run_args, context)]
