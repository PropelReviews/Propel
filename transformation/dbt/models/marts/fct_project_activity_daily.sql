-- Daily project activity across project trackers (Linear today; Jira later).
--
--   projects_created / projects_completed / projects_canceled
-- Grain includes `source` for multi-tool rollups.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date', 'source'],
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
        'linear' as source,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as created,
        0 as completed,
        0 as canceled
    from projects
    where created_at is not null

    union all

    select
        tenant_id,
        'linear' as source,
        (completed_at at time zone 'UTC')::date as activity_date,
        0 as created,
        1 as completed,
        0 as canceled
    from projects
    where completed_at is not null

    union all

    select
        tenant_id,
        'linear' as source,
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
    source,
    sum(created)::int as projects_created,
    sum(completed)::int as projects_completed,
    sum(canceled)::int as projects_canceled
from activity
group by tenant_id, activity_date, source
