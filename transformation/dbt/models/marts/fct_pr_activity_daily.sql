-- Daily pull-request activity per tenant.
--
--   prs_opened: PRs created that day (created_at)
--   prs_merged: PRs merged that day (merged_at)
--   prs_closed: PRs closed WITHOUT merging that day (closed_at, merged_at null)
--
-- Incremental delete+insert keyed on (tenant_id, activity_date): a
-- tenant-scoped run (--vars '{tenant_id: ...}', launched by the Dagster
-- analytics sensor) recomputes only that tenant's history and replaces its
-- rows; `dbt build --full-refresh` rebuilds every tenant.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with prs as (

    select *
    from {{ ref('stg_github_pull_requests') }}
    {% if var('tenant_id', none) %}
    where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

activity as (

    select
        tenant_id,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as opened,
        0 as merged,
        0 as closed
    from prs
    where created_at is not null

    union all

    select
        tenant_id,
        (merged_at at time zone 'UTC')::date as activity_date,
        0 as opened,
        1 as merged,
        0 as closed
    from prs
    where merged_at is not null

    union all

    select
        tenant_id,
        (closed_at at time zone 'UTC')::date as activity_date,
        0 as opened,
        0 as merged,
        1 as closed
    from prs
    where closed_at is not null and merged_at is null

)

select
    tenant_id,
    activity_date,
    sum(opened)::int as prs_opened,
    sum(merged)::int as prs_merged,
    sum(closed)::int as prs_closed
from activity
group by tenant_id, activity_date
