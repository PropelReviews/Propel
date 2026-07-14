-- Latest snapshot of every Linear project, one row per project.

select distinct on (tenant_id, payload ->> 'id')
    tenant_id,
    payload ->> 'id' as project_id,
    payload ->> 'name' as name,
    payload ->> 'url' as url,
    (payload ->> 'createdAt')::timestamptz as created_at,
    (payload ->> 'updatedAt')::timestamptz as updated_at,
    (payload ->> 'startedAt')::timestamptz as started_at,
    (payload ->> 'completedAt')::timestamptz as completed_at,
    (payload ->> 'canceledAt')::timestamptz as canceled_at,
    payload -> 'status' ->> 'name' as status_name,
    payload -> 'status' ->> 'type' as status_type,
    coalesce(
        payload -> 'lead' ->> 'id',
        payload -> 'lead' ->> 'email'
    ) as lead_id,
    fetched_at
from {{ source('propel', 'linear_projects') }}
where
    source = 'linear'
    and resource_type = 'projects'
    and payload ->> 'id' is not null
order by tenant_id asc, payload ->> 'id' asc, fetched_at desc
