-- Daily GitHub Actions workflow-run primitives per tenant.
--
--   runs_started:    workflow runs created that day
--   runs_completed:  runs whose latest snapshot is completed that day
--   runs_success:    completed with conclusion = success
--   runs_failure:    completed with conclusion in (failure, timed_out, cancelled)

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with runs as (

    select *
    from {{ ref('stg_github_workflow_runs') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

activity as (

    select
        tenant_id,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as started,
        0 as completed,
        0 as success,
        0 as failure
    from runs
    where created_at is not null

    union all

    select
        tenant_id,
        (updated_at at time zone 'UTC')::date as activity_date,
        0 as started,
        1 as completed,
        case when lower(coalesce(conclusion, '')) = 'success' then 1 else 0 end
            as success,
        case
            when lower(coalesce(conclusion, '')) in (
                'failure', 'timed_out', 'cancelled'
            ) then 1
            else 0
        end as failure
    from runs
    where
        updated_at is not null
        and lower(coalesce(status, '')) = 'completed'

)

select
    tenant_id,
    activity_date,
    sum(started)::int as runs_started,
    sum(completed)::int as runs_completed,
    sum(success)::int as runs_success,
    sum(failure)::int as runs_failure
from activity
group by tenant_id, activity_date
