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
    payload ->> 'title' as title,
    payload ->> 'state' as state,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'closed_at')::timestamptz as closed_at,
    (payload ->> 'merged_at')::timestamptz as merged_at,
    -- DORA lead-time proxy: hours from PR open to merge (null when unmerged).
    case
        when
            (payload ->> 'merged_at') is not null
            and (payload ->> 'created_at') is not null
            then extract(
                epoch from (
                    (payload ->> 'merged_at')::timestamptz
                    - (payload ->> 'created_at')::timestamptz
                )
            ) / 3600.0
    end as cycle_time_hours,
    -- Weak change-failure proxy: merged PRs whose title looks like a revert.
    -- Postgres POSIX regex has no \b word-boundary; use space/punct/end.
    coalesce(payload ->> 'title', '')
    ~* '^revert([[:space:][:punct:]]|$)' as is_revert,
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
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
