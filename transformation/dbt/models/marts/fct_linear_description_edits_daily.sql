-- Daily Linear issue description-edit activity per tenant.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with edits as (

    select *
    from {{ ref('stg_linear_description_edits') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

)

select
    tenant_id,
    (edited_at at time zone 'UTC')::date as activity_date,
    count(*)::int as description_edits
from edits
where edited_at is not null
group by tenant_id, (edited_at at time zone 'UTC')::date
