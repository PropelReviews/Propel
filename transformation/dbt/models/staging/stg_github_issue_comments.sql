-- Latest snapshot of every GitHub issue comment, one row per comment.
-- Distinct from pull_request_review_comments (line-level PR review discussion).

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as comment_node_id,
    (payload ->> 'id')::bigint as comment_id,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'updated_at')::timestamptz as updated_at,
    payload -> 'user' ->> 'login' as author_login,
    (payload ->> 'issue_number')::int as issue_number,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_issue_comments') }}
where
    source = 'github'
    and resource_type = 'issue_comments'
    and payload ->> 'node_id' is not null
    and payload ->> 'created_at' is not null
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
