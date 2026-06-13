-- Latest snapshot of every GitHub issue, one row per issue.
--
-- raw_record is append-only: each re-sync lands a new row, so the newest fetch
-- (by fetched_at) is the current state. GitHub's issues endpoint also returns
-- pull requests; exclude those via the pull_request key on the payload.
--
-- This view is global (all tenants); tenant scoping happens downstream in the
-- incremental marts so the view definition never depends on a run-time var.

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as issue_node_id,
    (payload ->> 'number')::int as issue_number,
    payload ->> 'title' as title,
    payload ->> 'state' as state,
    payload ->> 'state_reason' as state_reason,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'updated_at')::timestamptz as updated_at,
    (payload ->> 'closed_at')::timestamptz as closed_at,
    payload -> 'user' ->> 'login' as author_login,
    payload -> 'assignee' ->> 'login' as assignee_login,
    payload ->> 'html_url' as html_url,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_issues') }}
where
    source = 'github'
    and resource_type = 'issues'
    and payload ->> 'node_id' is not null
    and not (payload ? 'pull_request')
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
