-- Daily Linear comment activity per tenant.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with comments as (

    select *
    from {{ ref('stg_linear_comments') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

)

select
    tenant_id,
    (created_at at time zone 'UTC')::date as activity_date,
    count(*)::int as comments_created
from comments
where created_at is not null
group by tenant_id, (created_at at time zone 'UTC')::date
