# Meltano extraction

Pull-based extraction for Propel ingestion (landing only). Meltano runs Singer
taps and lands records through the custom `target-propel` loader, which writes
`raw_record` + thin `datapoint` envelopes to Postgres. No transforms happen here
— that is the (later) dbt layer's job.

## Layout

```
meltano/
├── meltano.yml          # plugins + jobs (github_sync, copilot_sync)
├── target-propel/       # custom Singer target → raw_record + datapoint
└── tap-github-copilot/  # custom tap for Copilot usage metrics (measurement)
```

`tap-github` is the MeltanoLabs variant pulled from the hub.

## How it runs

The orchestrator ([`app/ingestion`](../app/ingestion)) drives Meltano per
active `connected_accounts` row. It mints a GitHub App installation token, sets
the per-run environment, and invokes a job:

```bash
meltano run github_sync     # PRs, commits, issues, comments, reviews
meltano run copilot_sync    # Copilot per-user-day usage (measurement)
```

### Per-run environment (set by the orchestrator)

| Variable | Purpose |
|---|---|
| `GITHUB_INSTALLATION_TOKEN` | tap auth, minted fresh per run |
| `TAP_GITHUB_REPOSITORIES` | JSON array of `org/repo` for the installation |
| `TAP_GITHUB_START_DATE` | backfill window / watermark |
| `COPILOT_ORG` | org login for Copilot metrics |
| `PROPEL_DATABASE_URL` | sync `postgresql://` URL for `target-propel` |
| `PROPEL_TENANT_ID` | tenant the records belong to |
| `PROPEL_CONNECTED_ACCOUNT_ID` | source connection |
| `PROPEL_RUN_ID` | links landed rows to an `ingestion_run` |
| `PROPEL_SOURCE` | provider tag on landed rows (default `github`) |

## Incremental state

Meltano's `.meltano/state/` is the tap's incremental source of truth during a
run. The orchestrator persists the final watermark to `ingestion_run.cursor`
on success; the first run backfills `INGESTION_BACKFILL_DAYS` (Copilot is capped
by GitHub at ~28 days).

## Local setup

```bash
cd backend/meltano
pipx run meltano install        # or: meltano install
meltano run github_sync
```
