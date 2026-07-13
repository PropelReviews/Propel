-- Daily deployment frequency from GitHub Releases (DORA).
--
-- A deployment is a published (non-draft) release. Production deployments
-- further exclude prereleases. Bucketed by published_at (UTC day).
--
-- Incremental delete+insert keyed on (tenant_id, activity_date).

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date'],
) }}

with published as (

    select
        tenant_id,
        (published_at at time zone 'UTC')::date as activity_date,
        is_prerelease
    from {{ ref('stg_github_releases') }}
    where
        not is_draft
        and published_at is not null
        {% if var('tenant_id', none) %}
            and tenant_id = '{{ var("tenant_id") }}'::uuid
        {% endif %}

)

select
    tenant_id,
    activity_date,
    count(*)::int as releases_published,
    count(*) filter (where not is_prerelease)::int as production_releases
from published
group by tenant_id, activity_date
