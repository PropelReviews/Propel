-- L0 pull_request entity (canonical).
--
-- Enriches stg_github_pull_requests with first_review_at (first non-author
-- submitted review) and normalized field names for the metric config catalog.
-- One row per PR; global view (tenant scoping happens in metric models).

with prs as (

    select *
    from {{ ref('stg_github_pull_requests') }}

),

reviews as (

    select *
    from {{ ref('stg_github_reviews') }}

),

first_review as (

    select
        prs.tenant_id,
        prs.pr_node_id,
        min(reviews.submitted_at) as first_review_at,
        count(reviews.review_node_id)::int as review_count
    from prs
    left join reviews
        on
            prs.tenant_id = reviews.tenant_id
            and reviews.repo is not distinct from prs.repo
            and prs.pr_number = reviews.pull_request_number
            and (
                prs.author_login is null
                or reviews.reviewer_login is distinct from prs.author_login
            )
    group by prs.tenant_id, prs.pr_node_id

)

select
    prs.tenant_id,
    prs.pr_node_id as id,
    prs.repo,
    prs.author_login as author_id,
    case
        when prs.merged_at is not null then 'merged'
        when prs.state = 'closed' then 'closed'
        else 'open'
    end as state,
    null::int as additions,
    null::int as deletions,
    coalesce(first_review.review_count, 0)::int as review_count,
    prs.is_revert,
    prs.created_at as opened_at,
    first_review.first_review_at,
    prs.merged_at,
    prs.closed_at,
    prs.fetched_at
from prs
left join first_review
    on
        prs.tenant_id = first_review.tenant_id
        and prs.pr_node_id = first_review.pr_node_id
