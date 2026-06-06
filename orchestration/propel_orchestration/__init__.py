"""Dagster orchestration for Propel ingestion.

Dagster is the V2 scheduler: a long-running ECS service (daemon + webserver) that
triggers the same ``app.ingestion.orchestrator.run_all`` entrypoint hourly. The
extraction pipeline (Meltano taps + ``target-propel``) lives in ``backend/`` and
is unchanged; this project only schedules and observes it.
"""
