-- Latest snapshot of every GitHub pull request, one row per PR.
--
-- raw_record is append-only: each re-sync of a PR lands a new row, so the
-- newest fetch (by fetched_at) is the current state. We deliberately read
-- raw_record instead of datapoint here because datapoint events dedupe on
-- first ingest and never reflect later close/merge transitions.
--
-- This view is global (all tenants); tenant scoping happens downstream in the
-- incremental marts so the view definition never depends on a run-time var.

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as pr_node_id,
    (payload ->> 'number')::int as pr_number,
    payload ->> 'state' as state,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'closed_at')::timestamptz as closed_at,
    (payload ->> 'merged_at')::timestamptz as merged_at,
    payload -> 'user' ->> 'login' as author_login,
    coalesce(
        payload -> 'base' -> 'repo' ->> 'full_name',
        nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/')
    ) as repo,
    fetched_at
from {{ source('propel', 'raw_record') }}
where
    source = 'github'
    and resource_type = 'pull_requests'
    and payload ->> 'node_id' is not null
order by tenant_id, payload ->> 'node_id', fetched_at desc
