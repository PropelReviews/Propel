-- Latest snapshot of every Linear issue description edit (IssueHistory row
-- where updatedDescription is true), one row per history entry.

select distinct on (tenant_id, payload ->> 'id')
    tenant_id,
    payload ->> 'id' as edit_id,
    (payload ->> 'createdAt')::timestamptz as edited_at,
    coalesce(
        payload -> 'issue' ->> 'id',
        payload ->> 'issueId'
    ) as issue_id,
    payload -> 'issue' ->> 'identifier' as issue_identifier,
    coalesce(
        payload -> 'descriptionUpdatedBy' -> 0 ->> 'id',
        payload -> 'actor' ->> 'id',
        payload -> 'actor' ->> 'email'
    ) as editor_id,
    fetched_at
from {{ source('propel', 'linear_description_edits') }}
where
    source = 'linear'
    and resource_type = 'issue_description_edits'
    and payload ->> 'id' is not null
    and coalesce((payload ->> 'updatedDescription')::boolean, false)
order by tenant_id asc, payload ->> 'id' asc, fetched_at desc
