-- Latest snapshot of every GitHub Release, one row per release.
--
-- Releases are the DORA deployment-frequency signal: Actions release workflows
-- (and manual publishes) create these records. Drafts are kept in staging for
-- audit but excluded from the deployment-frequency mart until published.
--
-- raw_record is append-only; the newest fetch (by fetched_at) is current state.
-- This view is global (all tenants); tenant scoping happens downstream.

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as release_node_id,
    (payload ->> 'id')::bigint as release_id,
    payload ->> 'tag_name' as tag_name,
    payload ->> 'name' as release_name,
    coalesce((payload ->> 'draft')::boolean, false) as is_draft,
    coalesce((payload ->> 'prerelease')::boolean, false) as is_prerelease,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'published_at')::timestamptz as published_at,
    payload -> 'author' ->> 'login' as author_login,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_releases') }}
where
    source = 'github'
    and resource_type = 'releases'
    and payload ->> 'node_id' is not null
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
