"""Dask cluster integration: step-level executor + raw client resource.

``org_ingestion_job`` distributes its steps across an external Dask cluster
via ``dagster-dask``'s ``dask_executor``. The scheduler address comes from the
``DASK_SCHEDULER_ADDRESS`` env var — the ``dask-scheduler`` compose service
locally, Cloud Map DNS (``dask-scheduler.<namespace>``) on ECS. When the env
var is unset the executor falls back to an ephemeral in-process
``LocalCluster`` so a bare ``dagster dev`` keeps working with zero setup.

The Dask workers run the same image as the Dagster service (entrypoint mode
``dask-worker``), so steps can import ``app``/``propel_orchestration``, reach
Postgres, and shell out to Meltano exactly as the in-process executor did.
Each worker is a separate process, so the process-wide asyncio loop in
``jobs._run`` stays single-loop per step — no orchestrator changes needed.

``DaskClusterResource`` additionally exposes a raw ``distributed.Client`` for
ops that want in-op parallelism (``client.map``/``submit``) on the same
cluster, independent of the step-level distribution the executor provides.
"""

from __future__ import annotations

import os

from dagster import ConfigurableResource, ExecutorDefinition
from dagster_dask import dask_executor
from distributed import Client

DASK_SCHEDULER_ADDRESS_ENV = "DASK_SCHEDULER_ADDRESS"


def scheduler_address() -> str | None:
    """The shared Dask scheduler address, or None to use a local cluster."""
    return os.environ.get(DASK_SCHEDULER_ADDRESS_ENV) or None


class DaskClusterResource(ConfigurableResource):
    """Hands ops a ``distributed.Client`` connected to the shared cluster.

    ``scheduler_address`` overrides the ``DASK_SCHEDULER_ADDRESS`` env var;
    when both are empty the client spins up an ad-hoc ``LocalCluster`` (dev).
    """

    scheduler_address: str = ""

    def get_client(self) -> Client:
        address = self.scheduler_address or scheduler_address()
        if address:
            return Client(address, timeout="30s")
        return Client()


def build_dask_executor() -> ExecutorDefinition:
    """``dask_executor`` bound to the shared scheduler when one is configured.

    Evaluated at definition load time (daemon, webserver, and run workers all
    carry the same ``DASK_SCHEDULER_ADDRESS``), so jobs need no per-run
    ``execution`` config. Without the env var the unconfigured executor is
    returned, which creates a ``LocalCluster`` per run.
    """
    address = scheduler_address()
    if address:
        return dask_executor.configured(
            {"cluster": {"existing": {"address": address}}},
            name="dask_executor",
        )
    return dask_executor
