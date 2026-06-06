-- Latest snapshot of every GitHub pull-request review, one row per review.
--
-- raw_record is append-only: each re-sync lands a new row, so the newest fetch
-- (by fetched_at) is the current state. Pending reviews have no submitted_at and
-- are excluded — they are not yet a completed review event.
--
-- tap-github stamps org/repo/pull_request_number onto review records so we can
-- join back to stg_github_pull_requests without parsing pull_request_url.
--
-- This view is global (all tenants); tenant scoping happens downstream in the
-- incremental marts so the view definition never depends on a run-time var.

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as review_node_id,
    (payload ->> 'id')::bigint as review_id,
    payload ->> 'state' as state,
    (payload ->> 'submitted_at')::timestamptz as submitted_at,
    payload -> 'user' ->> 'login' as reviewer_login,
    (payload ->> 'pull_request_number')::int as pull_request_number,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_reviews') }}
where
    source = 'github'
    and resource_type = 'reviews'
    and payload ->> 'node_id' is not null
    and payload ->> 'submitted_at' is not null
    and coalesce(payload ->> 'state', '') <> 'PENDING'
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
