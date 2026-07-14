-- Daily ticket activity across issue trackers (GitHub Issues, Linear, …).
--
--   tickets_created:   tickets created that day
--   tickets_completed: tickets completed that day
--   tickets_canceled:  tickets canceled that day
--
-- Grain includes `source` so a future Jira (or other) tap lands in the same
-- mart without a new fact table. API responses sum across sources by default.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date', 'source'],
) }}

with github_issues as (

    select *
    from {{ ref('stg_github_issues') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

linear_issues as (

    select *
    from {{ ref('stg_linear_issues') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

activity as (

    -- GitHub: created
    select
        tenant_id,
        'github' as source,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as created,
        0 as completed,
        0 as canceled
    from github_issues
    where created_at is not null

    union all

    -- GitHub: completed (closed, not canceled)
    select
        tenant_id,
        'github' as source,
        (closed_at at time zone 'UTC')::date as activity_date,
        0 as created,
        1 as completed,
        0 as canceled
    from github_issues
    where
        closed_at is not null
        and coalesce(state_reason, '') <> 'not_planned'

    union all

    -- GitHub: canceled (closed as not_planned)
    select
        tenant_id,
        'github' as source,
        (closed_at at time zone 'UTC')::date as activity_date,
        0 as created,
        0 as completed,
        1 as canceled
    from github_issues
    where
        closed_at is not null
        and state_reason = 'not_planned'

    union all

    -- Linear: created
    select
        tenant_id,
        'linear' as source,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as created,
        0 as completed,
        0 as canceled
    from linear_issues
    where created_at is not null

    union all

    -- Linear: completed
    select
        tenant_id,
        'linear' as source,
        (completed_at at time zone 'UTC')::date as activity_date,
        0 as created,
        1 as completed,
        0 as canceled
    from linear_issues
    where completed_at is not null

    union all

    -- Linear: canceled
    select
        tenant_id,
        'linear' as source,
        (canceled_at at time zone 'UTC')::date as activity_date,
        0 as created,
        0 as completed,
        1 as canceled
    from linear_issues
    where canceled_at is not null

)

select
    tenant_id,
    activity_date,
    source,
    sum(created)::int as tickets_created,
    sum(completed)::int as tickets_completed,
    sum(canceled)::int as tickets_canceled
from activity
group by tenant_id, activity_date, source
