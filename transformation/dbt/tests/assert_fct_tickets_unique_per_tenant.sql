-- ticket_uid is unique within a tenant, not globally — the same GitHub/Linear
-- issue can appear under multiple tenants (e.g. shared org installs).
select
    tenant_id,
    ticket_uid,
    count(*) as row_count
from {{ ref('fct_tickets') }}
group by tenant_id, ticket_uid
having count(*) > 1
