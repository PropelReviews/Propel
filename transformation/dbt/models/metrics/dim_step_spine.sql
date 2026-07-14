-- Shared step spine for rolling-window metric models (M3).
-- Day and week steps covering the last history_days (default 730).

{{ config(materialized='table') }}

with bounds as (

    select
        (current_date - ({{ var('history_days', 730) }} || ' days')::interval)::date
            as start_date,
        current_date as end_date

),

day_spine as (

    select
        gs::date as step_date,
        'day'::text as step
    from bounds
    cross join lateral generate_series(
        bounds.start_date,
        bounds.end_date,
        interval '1 day'
    ) as gs

),

week_spine as (

    select
        date_trunc('week', gs)::date as step_date,
        'week'::text as step
    from bounds
    cross join lateral generate_series(
        bounds.start_date,
        bounds.end_date,
        interval '1 day'
    ) as gs
    group by 1

)

select * from day_spine
union all
select * from week_spine
