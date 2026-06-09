-- CI smoke check: assert the mart computed the expected daily aggregates from
-- ci/fixture_raw_record.sql. Raises (non-zero psql exit with ON_ERROR_STOP)
-- on any mismatch.

do $$
declare
    bad_rows int;
begin
    with expected (activity_date, prs_opened, prs_merged, prs_closed) as (
        values
            ('2026-01-05'::date, 2, 0, 0),  -- PR_1 + PR_2 opened (PR_1 dedup: latest fetch is open)
            ('2026-01-06'::date, 1, 1, 0),  -- PR_3 opened, PR_2 merged
            ('2026-01-07'::date, 0, 0, 1)   -- PR_3 closed without merge
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_pr_activity_daily f
        on f.activity_date = e.activity_date
    where
        f.tenant_id is distinct from 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
        or f.prs_opened is distinct from e.prs_opened
        or f.prs_merged is distinct from e.prs_merged
        or f.prs_closed is distinct from e.prs_closed;

    if bad_rows > 0 then
        raise exception 'fct_pr_activity_daily does not match expected fixture output (% mismatched rows)', bad_rows;
    end if;

    raise notice 'fct_pr_activity_daily matches expected fixture output';
end $$;
