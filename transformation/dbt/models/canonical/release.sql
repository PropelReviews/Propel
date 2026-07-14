-- L0 release entity (canonical) — GitHub Releases as deployment-frequency proxy.

select
    tenant_id,
    release_node_id as id,
    repo,
    is_draft,
    is_prerelease,
    published_at,
    created_at,
    fetched_at
from {{ ref('stg_github_releases') }}
