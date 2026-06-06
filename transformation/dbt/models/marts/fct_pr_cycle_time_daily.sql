-- Daily PR cycle-time primitives (DORA lead-time-for-changes proxy).
--
-- For each tenant/day of merges:
--   prs_merged:            count of PRs merged that day
--   median_cycle_time_hours / avg_cycle_time_hours / p90_cycle_time_hours:
--                          open → merge duration in hours
--
-- True DORA lead time is commit → production deploy. Until we ingest deploys,
-- PR open → merge is the inspectable proxy Propel can compute from GitHub PRs.
--
-- Incremental delete+insert keyed on (tenant_id, activity_date): a
-- tenant-scoped run (--vars '{tenant_id: ...}') recomputes only that tenant's
-- history; `dbt build --full-refresh` rebuilds every tenant.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with merged as (

    select
        tenant_id,
        (merged_at at time zone 'UTC')::date as activity_date,
        cycle_time_hours
    from {{ ref('stg_github_pull_requests') }}
    where
        merged_at is not null
        and cycle_time_hours is not null
        and cycle_time_hours >= 0
        {% if var('tenant_id', none) %}
            and tenant_id = '{{ var("tenant_id") }}'::uuid
        {% endif %}

)

select
    tenant_id,
    activity_date,
    count(*)::int as prs_merged,
    percentile_cont(0.5) within group (
        order by cycle_time_hours
    )::float8 as median_cycle_time_hours,
    avg(cycle_time_hours)::float8 as avg_cycle_time_hours,
    percentile_cont(0.9) within group (
        order by cycle_time_hours
    )::float8 as p90_cycle_time_hours
from merged
group by tenant_id, activity_date
