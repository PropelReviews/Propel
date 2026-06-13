-- Latest snapshot of every Linear issue, one row per issue.
--
-- raw_record is append-only: each re-sync lands a new row, so the newest fetch
-- (by fetched_at) is the current state.
--
-- This view is global (all tenants); tenant scoping happens downstream in the
-- incremental marts so the view definition never depends on a run-time var.

select distinct on (tenant_id, payload ->> 'id')
    tenant_id,
    payload ->> 'id' as issue_id,
    payload ->> 'identifier' as identifier,
    payload ->> 'title' as title,
    payload -> 'state' ->> 'name' as state_name,
    payload -> 'state' ->> 'type' as state_type,
    (payload ->> 'createdAt')::timestamptz as created_at,
    (payload ->> 'updatedAt')::timestamptz as updated_at,
    (payload ->> 'completedAt')::timestamptz as completed_at,
    (payload ->> 'canceledAt')::timestamptz as canceled_at,
    (payload ->> 'priority')::int as priority,
    (payload ->> 'estimate')::numeric as estimate,
    payload ->> 'url' as url,
    payload -> 'team' ->> 'key' as team_key,
    coalesce(
        payload -> 'creator' ->> 'email',
        payload -> 'creator' ->> 'displayName',
        payload -> 'creator' ->> 'name'
    ) as creator,
    coalesce(
        payload -> 'assignee' ->> 'email',
        payload -> 'assignee' ->> 'displayName',
        payload -> 'assignee' ->> 'name'
    ) as assignee,
    fetched_at
from {{ source('propel', 'linear_issues') }}
where
    source = 'linear'
    and resource_type = 'issues'
    and payload ->> 'id' is not null
order by tenant_id asc, payload ->> 'id' asc, fetched_at desc
