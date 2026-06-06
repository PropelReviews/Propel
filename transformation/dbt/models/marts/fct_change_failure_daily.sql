-- Daily change-failure proxy (DORA change-fail-rate stand-in).
--
-- True CFR needs production incidents / failed deploys. Until those land,
-- Propel counts merged PRs whose title looks like a revert
-- (`^Revert` followed by space/punct/end) as failed changes, bucketed by
-- merge day:
--
--   prs_merged:           merges that day
--   prs_reverted:         revert-titled merges that day
--   change_failure_rate:  prs_reverted / prs_merged (null when no merges)
--
-- Incremental delete+insert keyed on (tenant_id, activity_date).

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with merged as (

    select
        tenant_id,
        (merged_at at time zone 'UTC')::date as activity_date,
        is_revert
    from {{ ref('stg_github_pull_requests') }}
    where
        merged_at is not null
        {% if var('tenant_id', none) %}
            and tenant_id = '{{ var("tenant_id") }}'::uuid
        {% endif %}

)

select
    tenant_id,
    activity_date,
    count(*)::int as prs_merged,
    count(*) filter (where is_revert)::int as prs_reverted,
    case
        when count(*) = 0 then null
        else (count(*) filter (where is_revert))::float8 / count(*)::float8
    end as change_failure_rate
from merged
group by tenant_id, activity_date
