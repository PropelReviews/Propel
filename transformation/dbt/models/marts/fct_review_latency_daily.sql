-- Daily review-latency primitives (DORA lead-time breakdown / review flow).
--
-- For each tenant/day when a PR received its first submitted review:
--   prs_first_reviewed:                 PRs whose first review landed that day
--   median_time_to_first_review_hours:  open → first review (excludes author
--                                       self-reviews when author is known)
--   reviews_submitted:                  all submitted reviews that day
--
-- Incremental delete+insert keyed on (tenant_id, activity_date).

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

reviews as (

    select *
    from {{ ref('stg_github_reviews') }}
    {% if var('tenant_id', none) %}
        where tenant_id = '{{ var("tenant_id") }}'::uuid
    {% endif %}

),

first_review as (

    select
        prs.tenant_id,
        prs.pr_node_id,
        prs.created_at,
        min(reviews.submitted_at) as first_reviewed_at,
        extract(
            epoch from (min(reviews.submitted_at) - prs.created_at)
        ) / 3600.0 as time_to_first_review_hours
    from prs
    inner join reviews
        on
            prs.tenant_id = reviews.tenant_id
            and reviews.repo is not distinct from prs.repo
            and prs.pr_number = reviews.pull_request_number
            and (
                prs.author_login is null
                or reviews.reviewer_login is distinct from prs.author_login
            )
    where prs.created_at is not null
    group by prs.tenant_id, prs.pr_node_id, prs.created_at

),

first_review_daily as (

    select
        tenant_id,
        (first_reviewed_at at time zone 'UTC')::date as activity_date,
        count(*)::int as prs_first_reviewed,
        percentile_cont(0.5) within group (
            order by time_to_first_review_hours
        )::float8 as median_time_to_first_review_hours
    from first_review
    where
        first_reviewed_at is not null
        and time_to_first_review_hours is not null
        and time_to_first_review_hours >= 0
    group by tenant_id, (first_reviewed_at at time zone 'UTC')::date

),

reviews_daily as (

    select
        tenant_id,
        (submitted_at at time zone 'UTC')::date as activity_date,
        count(*)::int as reviews_submitted
    from reviews
    where submitted_at is not null
    group by tenant_id, (submitted_at at time zone 'UTC')::date

)

select
    coalesce(f.tenant_id, r.tenant_id) as tenant_id,
    coalesce(f.activity_date, r.activity_date) as activity_date,
    coalesce(f.prs_first_reviewed, 0)::int as prs_first_reviewed,
    f.median_time_to_first_review_hours,
    coalesce(r.reviews_submitted, 0)::int as reviews_submitted
from first_review_daily as f
full outer join reviews_daily as r
    on
        f.tenant_id = r.tenant_id
        and f.activity_date = r.activity_date
