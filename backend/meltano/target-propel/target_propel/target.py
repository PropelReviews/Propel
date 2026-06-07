"""target-propel Singer target entrypoint.

Per-run context (database, tenant, connected account, run id) is supplied by the
orchestrator through PROPEL_* environment variables rather than Singer config,
so the same target binary works unchanged for every tenant.
"""

from __future__ import annotations

from singer_sdk import typing as th
from singer_sdk.target_base import Target

from target_propel.sinks import PropelSink


class TargetPropel(Target):
    name = "target-propel"
    default_sink_class = PropelSink

    # Context is read from PROPEL_* env vars (see module docstring); no required
    # Singer config. Kept as an empty schema so Meltano is happy.
    config_jsonschema = th.PropertiesList().to_dict()


if __name__ == "__main__":
    TargetPropel.cli()
