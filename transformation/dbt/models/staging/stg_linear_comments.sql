-- Latest snapshot of every Linear comment, one row per comment.

select distinct on (tenant_id, payload ->> 'id')
    tenant_id,
    payload ->> 'id' as comment_id,
    (payload ->> 'createdAt')::timestamptz as created_at,
    (payload ->> 'updatedAt')::timestamptz as updated_at,
    (payload ->> 'editedAt')::timestamptz as edited_at,
    coalesce(
        payload ->> 'issueId',
        payload -> 'issue' ->> 'id'
    ) as issue_id,
    payload -> 'issue' ->> 'identifier' as issue_identifier,
    coalesce(
        payload ->> 'projectId',
        payload -> 'project' ->> 'id'
    ) as project_id,
    coalesce(
        payload -> 'user' ->> 'id',
        payload -> 'user' ->> 'email',
        payload -> 'externalUser' ->> 'id'
    ) as author_id,
    fetched_at
from {{ source('propel', 'linear_comments') }}
where
    source = 'linear'
    and resource_type = 'comments'
    and payload ->> 'id' is not null
order by tenant_id asc, payload ->> 'id' asc, fetched_at desc
