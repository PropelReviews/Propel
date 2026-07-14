-- Shared step spine for rolling-window metric models (M3).
-- Day and week steps covering the last history_days (default 730).

{{ config(materialized='table') }}

with day_spine as (

    select
        gs::date as step_date,
        'day'::text as step
    from generate_series(
        (current_date - ({{ var('history_days', 730) }} || ' days')::interval)::date,
        current_date,
        interval '1 day'
    ) as gs

),

week_spine as (

    select
        date_trunc('week', step_date)::date as step_date,
        'week'::text as step
    from day_spine
    group by 1

)

select * from day_spine
union all
select * from week_spine
