-- Unified ticket entity across GitHub issues and Linear issues.
--
-- One row per ticket per tenant. Incremental delete+insert keyed on
-- (tenant_id, ticket_uid): a tenant-scoped run (--vars '{tenant_id: ...}',
-- launched by the Dagster analytics sensor) recomputes only that tenant's rows;
-- `dbt build --full-refresh` rebuilds every tenant.

{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['tenant_id', 'ticket_uid'],
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

github_tickets as (

    select
        tenant_id,
        'github' as source,
        issue_node_id as external_id,
        concat(repo, '#', issue_number::text) as external_key,
        title,
        html_url as url,
        state as raw_state,
        case
            when state = 'open' then 'open'
            when state = 'closed' and state_reason = 'not_planned' then 'canceled'
            when state = 'closed' then 'done'
            else 'open'
        end as status,
        author_login as creator,
        assignee_login as assignee,
        created_at,
        updated_at,
        closed_at as completed_at,
        null::timestamptz as canceled_at,
        null::text as team,
        null::int as priority,
        null::numeric as estimate
    from github_issues

),

linear_tickets as (

    select
        tenant_id,
        'linear' as source,
        issue_id as external_id,
        identifier as external_key,
        title,
        url,
        coalesce(state_name, state_type) as raw_state,
        case
            when state_type = 'started' then 'in_progress'
            when state_type = 'completed' then 'done'
            when state_type = 'canceled' then 'canceled'
            else 'open'
        end as status,
        creator,
        assignee,
        created_at,
        updated_at,
        completed_at,
        canceled_at,
        team_key as team,
        priority,
        estimate
    from linear_issues

),

combined as (

    select * from github_tickets
    union all
    select * from linear_tickets

)

select
    tenant_id,
    source || ':' || external_id as ticket_uid,
    source,
    external_id,
    external_key,
    title,
    url,
    raw_state,
    status,
    creator,
    assignee,
    created_at,
    updated_at,
    completed_at,
    canceled_at,
    team,
    priority,
    estimate
from combined
