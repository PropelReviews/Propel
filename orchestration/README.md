# Propel ingestion orchestration (Dagster)

The **`ingestion` service** is a always-on Dagster process. It schedules and
runs extraction workflows **inside its own container** — no separate cron or
EventBridge tasks. Meltano, the taps, and `target-propel` stay in
`backend/meltano/`; Dagster ops call `app.ingestion.orchestrator` directly.

## Per-org DAG

For each active GitHub `connected_account`, the hourly `ingestion_job` runs:

```
github_sync → github_org_sync → github_user_profiles_sync → copilot_sync
```

Definitions: [`backend/app/ingestion/dagster/definitions.py`](../backend/app/ingestion/dagster/definitions.py).

## Local dev

```bash
docker compose up -d postgres backend ingestion
docker logs -f propel-ingestion
```

Dagster UI: http://localhost:3000

Manual run (bypasses the schedule, same orchestrator code):

```bash
docker compose exec ingestion python -m app.ingestion.cli run
```

## AWS (beta/prod)

When `ingestion_enabled = true` (default), Terraform provisions an always-on ECS
service (`propel-<env>-ingestion`) from the same API image with
`command = ["ingestion"]`.

Observability: structured JSON logs + PostHog OTLP (`OTEL_SERVICE_NAME=propel-ingestion`).
