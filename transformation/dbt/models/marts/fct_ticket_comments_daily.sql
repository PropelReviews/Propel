-- Daily ticket-comment activity across issue trackers.
--
-- Grain includes `source` so GitHub / Linear / future Jira land in one mart.
-- Excludes GitHub PR review comments (those stay in fct_review_comments_daily).

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'activity_date', 'source'],
) }}

with github_comments as (

    select *
    from {{ ref('stg_github_issue_comments') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

linear_comments as (

    select *
    from {{ ref('stg_linear_comments') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

activity as (

    select
        tenant_id,
        'github' as source,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as comments_created
    from github_comments
    where created_at is not null

    union all

    select
        tenant_id,
        'linear' as source,
        (created_at at time zone 'UTC')::date as activity_date,
        1 as comments_created
    from linear_comments
    where created_at is not null

)

select
    tenant_id,
    activity_date,
    source,
    sum(comments_created)::int as comments_created
from activity
group by tenant_id, activity_date, source
