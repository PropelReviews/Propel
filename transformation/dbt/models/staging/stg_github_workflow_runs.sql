-- Latest snapshot of every GitHub Actions workflow run, one row per run.
--
-- Primitive CI/CD activity signal: status/conclusion, triggering event, and
-- timestamps. Distinct from Releases (DORA deployment frequency).

select distinct on (tenant_id, payload ->> 'node_id')
    tenant_id,
    payload ->> 'node_id' as run_node_id,
    (payload ->> 'id')::bigint as run_id,
    payload ->> 'name' as workflow_name,
    payload ->> 'status' as status,
    payload ->> 'conclusion' as conclusion,
    payload ->> 'event' as event,
    (payload ->> 'run_number')::int as run_number,
    (payload ->> 'created_at')::timestamptz as created_at,
    (payload ->> 'updated_at')::timestamptz as updated_at,
    coalesce(
        payload -> 'actor' ->> 'login',
        payload -> 'triggering_actor' ->> 'login'
    ) as actor_login,
    payload ->> 'head_branch' as head_branch,
    payload ->> 'head_sha' as head_sha,
    nullif(concat(payload ->> 'org', '/', payload ->> 'repo'), '/') as repo,
    fetched_at
from {{ source('propel', 'github_workflow_runs') }}
where
    source = 'github'
    and resource_type = 'workflow_runs'
    and payload ->> 'node_id' is not null
order by tenant_id asc, payload ->> 'node_id' asc, fetched_at desc
