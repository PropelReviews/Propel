-- CI smoke check: assert the marts computed the expected daily aggregates from
-- ci/fixture_raw_record.sql. Raises (non-zero psql exit with ON_ERROR_STOP)
-- on any mismatch.

do $$
declare
    bad_rows int;
begin
    -- Throughput / deployment-frequency proxy
    with expected (activity_date, prs_opened, prs_merged, prs_closed) as (
        values
            -- PR_1 + PR_2 opened (PR_1 dedup: latest fetch is open)
            ('2026-01-05'::date, 2, 0, 0),
            -- PR_3/4/5 opened; PR_2/4/5 merged
            ('2026-01-06'::date, 3, 3, 0),
            -- PR_3 closed without merge
            ('2026-01-07'::date, 0, 0, 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_pr_activity_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.prs_opened is distinct from e.prs_opened
        or f.prs_merged is distinct from e.prs_merged
        or f.prs_closed is distinct from e.prs_closed
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_pr_activity_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_pr_activity_daily matches expected fixture output';

    -- Lead-time proxy: cycle times on 2026-01-06 are 24h (PR_2), 2h (PR_4), 1h (PR_5)
    -- → median 2, avg 9, p90 19.6
    with expected (
        activity_date, prs_merged, median_h, avg_h, p90_h
    ) as (
        values
            ('2026-01-06'::date, 3, 2.0::float8, 9.0::float8, 19.6::float8)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_pr_cycle_time_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.prs_merged is distinct from e.prs_merged
        or abs(f.median_cycle_time_hours - e.median_h) > 0.001
        or abs(f.avg_cycle_time_hours - e.avg_h) > 0.001
        or abs(f.p90_cycle_time_hours - e.p90_h) > 0.001
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_pr_cycle_time_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_pr_cycle_time_daily matches expected fixture output';

    -- Review latency: PR_2 first non-author review 6h (2026-01-05); PR_5 0.5h
    -- (2026-01-06). Submitted reviews: 2 on Jan 5, 1 on Jan 6 (pending excluded).
    with expected (
        activity_date, prs_first_reviewed, median_h, reviews_submitted
    ) as (
        values
            ('2026-01-05'::date, 1, 6.0::float8, 2),
            ('2026-01-06'::date, 1, 0.5::float8, 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_review_latency_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.prs_first_reviewed is distinct from e.prs_first_reviewed
        or f.reviews_submitted is distinct from e.reviews_submitted
        or abs(f.median_time_to_first_review_hours - e.median_h) > 0.001
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_review_latency_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_review_latency_daily matches expected fixture output';

    -- Change-failure proxy: 1 revert of 3 merges on 2026-01-06 → 1/3
    with expected (activity_date, prs_merged, prs_reverted, cfr) as (
        values
            ('2026-01-06'::date, 3, 1, (1.0 / 3.0)::float8)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_change_failure_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.prs_merged is distinct from e.prs_merged
        or f.prs_reverted is distinct from e.prs_reverted
        or abs(f.change_failure_rate - e.cfr) > 0.001
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_change_failure_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_change_failure_daily matches expected fixture output';

    -- Deployment frequency: REL_1 production on 2026-01-06; REL_2 prerelease on
    -- 2026-01-07; draft excluded.
    with expected (
        activity_date, releases_published, production_releases
    ) as (
        values
            ('2026-01-06'::date, 1, 1),
            ('2026-01-07'::date, 1, 0)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_deployment_frequency_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.releases_published is distinct from e.releases_published
        or f.production_releases is distinct from e.production_releases
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_deployment_frequency_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_deployment_frequency_daily matches expected fixture output';

    -- Review comments: 1 on Jan 5, 1 on Jan 6
    with expected (activity_date, review_comments_created) as (
        values
            ('2026-01-05'::date, 1),
            ('2026-01-06'::date, 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_review_comments_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.review_comments_created is distinct from e.review_comments_created
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_review_comments_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_review_comments_daily matches expected fixture output';

    -- Workflow runs: WFR_1 started+completed success on Jan 6; WFR_2 failure on Jan 7
    with expected (
        activity_date, runs_started, runs_completed, runs_success, runs_failure
    ) as (
        values
            ('2026-01-06'::date, 1, 1, 1, 0),
            ('2026-01-07'::date, 1, 1, 0, 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_workflow_runs_daily f
        on f.activity_date = e.activity_date
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.runs_started is distinct from e.runs_started
        or f.runs_completed is distinct from e.runs_completed
        or f.runs_success is distinct from e.runs_success
        or f.runs_failure is distinct from e.runs_failure
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_workflow_runs_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_workflow_runs_daily matches expected fixture output';

    -- Ticket activity (GitHub + Linear), grain (date, source)
    with expected (
        activity_date, source, tickets_created, tickets_completed, tickets_canceled
    ) as (
        values
            ('2026-01-02'::date, 'linear', 1, 0, 0),
            ('2026-01-03'::date, 'github', 1, 0, 0),
            ('2026-01-04'::date, 'github', 1, 0, 0),
            ('2026-01-04'::date, 'linear', 1, 0, 0),
            ('2026-01-05'::date, 'github', 0, 0, 1),
            ('2026-01-05'::date, 'linear', 0, 0, 1),
            ('2026-01-06'::date, 'linear', 0, 1, 0)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_ticket_activity_daily f
        on f.activity_date = e.activity_date
        and f.source = e.source
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.tickets_created is distinct from e.tickets_created
        or f.tickets_completed is distinct from e.tickets_completed
        or f.tickets_canceled is distinct from e.tickets_canceled
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_ticket_activity_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_ticket_activity_daily matches expected fixture output';

    -- Ticket comments: GitHub IC_1 on Jan 4; Linear comments on Jan 5 and 6
    with expected (activity_date, source, comments_created) as (
        values
            ('2026-01-04'::date, 'github', 1),
            ('2026-01-05'::date, 'linear', 1),
            ('2026-01-06'::date, 'linear', 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_ticket_comments_daily f
        on f.activity_date = e.activity_date
        and f.source = e.source
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.comments_created is distinct from e.comments_created
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_ticket_comments_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_ticket_comments_daily matches expected fixture output';

    -- Project activity (Linear today)
    with expected (
        activity_date, source, projects_created, projects_completed, projects_canceled
    ) as (
        values
            ('2026-01-01'::date, 'linear', 1, 0, 0),
            ('2026-01-06'::date, 'linear', 0, 1, 0)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_project_activity_daily f
        on f.activity_date = e.activity_date
        and f.source = e.source
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.projects_created is distinct from e.projects_created
        or f.projects_completed is distinct from e.projects_completed
        or f.projects_canceled is distinct from e.projects_canceled
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_project_activity_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_project_activity_daily matches expected fixture output';

    -- Ticket description edits (Linear today)
    with expected (activity_date, source, description_edits) as (
        values
            ('2026-01-05'::date, 'linear', 1)
    )
    select count(*) into bad_rows
    from expected e
    full outer join analytics.fct_ticket_description_edits_daily f
        on f.activity_date = e.activity_date
        and f.source = e.source
        and f.tenant_id = 'aaaaaaaa-0000-0000-0000-000000000001'::uuid
    where
        f.description_edits is distinct from e.description_edits
        or e.activity_date is null
        or f.activity_date is null;

    if bad_rows > 0 then
        raise exception
            'fct_ticket_description_edits_daily does not match expected fixture output (% mismatched rows)',
            bad_rows;
    end if;

    raise notice 'fct_ticket_description_edits_daily matches expected fixture output';
end $$;
