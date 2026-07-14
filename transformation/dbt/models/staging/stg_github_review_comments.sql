-- Latest snapshot of every GitHub pull-request review comment, one row per
-- comment. Distinct from issue_comments and from the review itself — these are
-- line-level discussion on a PR diff.
--
-- raw_record is append-only; the newest fetch (by fetched_at) is current state.

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as comment_node_id,
    (payload ->> 'id')::bigint as comment_id,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'updated_at')::timestamptz as updated_at,
    payload -> 'user' ->> 'login' as author_login,
    (payload ->> 'pull_request_number')::int as pull_request_number,
    (payload ->> 'pull_request_review_id')::bigint as pull_request_review_id,
    payload ->> 'path' as path,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_review_comments') }}
where
    source = 'github'
    and resource_type = 'pull_request_review_comments'
    and payload ->> 'node_id' is not null
    and payload ->> 'created_at' is not null
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
