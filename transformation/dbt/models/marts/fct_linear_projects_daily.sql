-- Daily Linear project activity per tenant.
--
--   projects_created:   projects created that day
--   projects_completed: projects completed that day
--   projects_canceled:  projects canceled that day

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with projects as (

    select *
    from {{ ref('stg_linear_projects') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

activity as (

    select
        tenant_id,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as created,
        0 as completed,
        0 as canceled
    from projects
    where created_at is not null

    union all

    select
        tenant_id,
        (completed_at at time zone 'UTC')::date as activity_date,
        0 as created,
        1 as completed,
        0 as canceled
    from projects
    where completed_at is not null

    union all

    select
        tenant_id,
        (canceled_at at time zone 'UTC')::date as activity_date,
        0 as created,
        0 as completed,
        1 as canceled
    from projects
    where canceled_at is not null

)

select
    tenant_id,
    activity_date,
    sum(created)::int as projects_created,
    sum(completed)::int as projects_completed,
    sum(canceled)::int as projects_canceled
from activity
group by tenant_id, activity_date
