# Meltano extraction

Pull-based extraction for Propel ingestion (landing only). Meltano runs Singer
taps and lands records through the custom `target-propel` loader, which writes
`raw_record` + thin `datapoint` envelopes to Postgres. No transforms happen here
— that is the (later) dbt layer's job.

## Layout

```
meltano/
├── meltano.yml          # plugins + jobs (github_org_sync, github_user_profiles_sync,
│                        #   github_commits_sync, github_pull_requests_sync,
│                        #   github_issues_sync, github_releases_sync, copilot_sync)
├── target-propel/       # custom Singer target → raw_record + datapoint
└── tap-github-copilot/  # custom tap for Copilot usage metrics (measurement)
```

`tap-github` is the MeltanoLabs variant pulled from the hub. Because the tap
requires exactly one discovery mode per invocation, the base `tap-github`
(auth + watermark only) is inherited by children that each set one mode and its
own stream selection. Repo activity is split per resource so each runs as its
own granular Meltano job / Dagster op: `tap-github-commits` (`commits`),
`tap-github-pull-requests` (`pull_requests`, `reviews`,
`pull_request_review_comments`), `tap-github-issues` (`issues`,
`issue_comments`), and `tap-github-releases` (`releases`) — all over
`repositories`. Org/user modes stay as `tap-github-org` (organizations →
`organization_members`) and `tap-github-users` (`user_usernames` → `users`).

## How it runs

The orchestrator ([`app/ingestion`](../app/ingestion)) drives Meltano per
active `connected_accounts` row. It mints a GitHub App installation token, sets
the per-run environment, and invokes a job:

```bash
meltano run github_org_sync            # org member roster (organization_members)
meltano run github_user_profiles_sync  # member name/email profiles (users)
meltano run github_commits_sync        # commits across the installation's repos
meltano run github_pull_requests_sync  # PRs + reviews + review comments
meltano run github_issues_sync         # issues + issue comments
meltano run github_releases_sync       # GitHub Releases (deployment frequency)
meltano run copilot_sync               # Copilot per-user-day usage (measurement)
```

After `github_user_profiles_sync` the orchestrator reconciles the roster into
`external_identities` and tenant memberships (see
[`docs/backend/data-model.md`](../../docs/backend/data-model.md#github-identity-linking-migration-003)).
The org/admin lookups need the GitHub App's **Organization → Members: Read-only**
permission.

### Per-run environment (set by the orchestrator)

| Variable | Purpose |
|---|---|
| `GITHUB_INSTALLATION_TOKEN` | tap auth, minted fresh per run |
| `TAP_GITHUB_REPOSITORIES` | JSON array of `org/repo` for the installation |
| `TAP_GITHUB_ORGANIZATIONS` | JSON array of org logins (org member roster) |
| `TAP_GITHUB_USER_USERNAMES` | JSON array of logins (member profile enrichment) |
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
meltano run github_commits_sync
```
