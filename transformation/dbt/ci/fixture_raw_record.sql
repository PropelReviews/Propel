-- CI fixture: minimal copy of the ingestion landing table plus a few PR
-- payloads so `dbt build` exercises the real staging/mart SQL.
-- Mirrors backend/app/models (raw_record) — keep in sync if that table changes.

create table if not exists public.raw_record (
    id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    source varchar(50) not null,
    resource_type varchar(100) not null,
    source_id varchar(255),
    payload jsonb not null,
    fetched_at timestamptz not null default now(),
    run_id uuid
);

-- Tenant aaaaaaaa-…: three PRs covering open, merged, and closed-without-merge,
-- plus a stale duplicate of PR_1 to verify dedup picks the latest fetch.
insert into public.raw_record (tenant_id, source, resource_type, source_id, payload, fetched_at)
values
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_1',
    '{"node_id": "PR_1", "number": 1, "title": "Broken WIP", "state": "closed",
      "created_at": "2026-01-05T10:00:00Z", "closed_at": "2026-01-05T11:00:00Z",
      "merged_at": null, "user": {"login": "alice"}, "org": "acme", "repo": "api"}',
    '2026-01-05T12:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_1',
    '{"node_id": "PR_1", "number": 1, "title": "Broken WIP", "state": "open",
      "created_at": "2026-01-05T10:00:00Z", "closed_at": null,
      "merged_at": null, "user": {"login": "alice"}, "org": "acme", "repo": "api"}',
    '2026-01-06T12:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_2',
    '{"node_id": "PR_2", "number": 2, "title": "Add auth", "state": "closed",
      "created_at": "2026-01-05T09:00:00Z", "closed_at": "2026-01-06T09:00:00Z",
      "merged_at": "2026-01-06T09:00:00Z", "user": {"login": "bob"}, "org": "acme", "repo": "api"}',
    '2026-01-06T10:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_3',
    '{"node_id": "PR_3", "number": 3, "title": "WIP experiment", "state": "closed",
      "created_at": "2026-01-06T08:00:00Z", "closed_at": "2026-01-07T08:00:00Z",
      "merged_at": null, "user": {"login": "carol"}, "org": "acme", "repo": "web"}',
    '2026-01-07T09:00:00Z'
),
-- Revert merge (change-failure proxy) + a second same-day merge for percentiles.
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_4',
    '{"node_id": "PR_4", "number": 4, "title": "Revert \"Add auth\"", "state": "closed",
      "created_at": "2026-01-06T12:00:00Z", "closed_at": "2026-01-06T14:00:00Z",
      "merged_at": "2026-01-06T14:00:00Z", "user": {"login": "alice"}, "org": "acme", "repo": "api"}',
    '2026-01-06T15:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_5',
    '{"node_id": "PR_5", "number": 5, "title": "Docs tweak", "state": "closed",
      "created_at": "2026-01-06T10:00:00Z", "closed_at": "2026-01-06T11:00:00Z",
      "merged_at": "2026-01-06T11:00:00Z", "user": {"login": "carol"}, "org": "acme", "repo": "web"}',
    '2026-01-06T12:00:00Z'
),
-- Reviews: first non-author review on PR_2; author self-review ignored for latency.
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'reviews', 'REV_1',
    '{"node_id": "REV_1", "id": 1, "state": "COMMENTED",
      "submitted_at": "2026-01-05T12:00:00Z", "user": {"login": "bob"},
      "pull_request_number": 2, "org": "acme", "repo": "api"}',
    '2026-01-05T13:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'reviews', 'REV_2',
    '{"node_id": "REV_2", "id": 2, "state": "APPROVED",
      "submitted_at": "2026-01-05T15:00:00Z", "user": {"login": "alice"},
      "pull_request_number": 2, "org": "acme", "repo": "api"}',
    '2026-01-05T16:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'reviews', 'REV_3',
    '{"node_id": "REV_3", "id": 3, "state": "APPROVED",
      "submitted_at": "2026-01-06T10:30:00Z", "user": {"login": "bob"},
      "pull_request_number": 5, "org": "acme", "repo": "web"}',
    '2026-01-06T11:00:00Z'
),
-- Pending review must be excluded from staging.
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'reviews', 'REV_PENDING',
    '{"node_id": "REV_PENDING", "id": 99, "state": "PENDING",
      "user": {"login": "alice"}, "pull_request_number": 5, "org": "acme", "repo": "web"}',
    '2026-01-06T11:00:00Z'
),
-- GitHub issues (exclude PR-shaped rows via pull_request key in staging)
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'issues', 'ISSUE_1',
    '{"node_id": "ISSUE_1", "number": 10, "title": "Fix login", "state": "open",
      "created_at": "2026-01-04T10:00:00Z", "updated_at": "2026-01-04T10:00:00Z",
      "user": {"login": "alice"}, "assignee": {"login": "bob"}, "org": "acme", "repo": "api",
      "html_url": "https://github.com/acme/api/issues/10"}',
    '2026-01-04T12:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'issues', 'ISSUE_2',
    '{"node_id": "ISSUE_2", "number": 11, "title": "Wont fix", "state": "closed",
      "state_reason": "not_planned", "created_at": "2026-01-03T10:00:00Z",
      "updated_at": "2026-01-05T10:00:00Z", "closed_at": "2026-01-05T10:00:00Z",
      "user": {"login": "carol"}, "org": "acme", "repo": "web",
      "html_url": "https://github.com/acme/web/issues/11"}',
    '2026-01-05T11:00:00Z'
),
-- Linear issues
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'linear', 'issues', 'lin-issue-1',
    '{"id": "lin-issue-1", "identifier": "ENG-42", "title": "Ship tickets mart",
      "createdAt": "2026-01-02T10:00:00Z", "updatedAt": "2026-01-06T10:00:00Z",
      "completedAt": "2026-01-06T10:00:00Z", "priority": 2, "estimate": 3,
      "url": "https://linear.app/acme/issue/ENG-42",
      "state": {"name": "Done", "type": "completed"},
      "team": {"key": "ENG"},
      "creator": {"email": "alice@acme.com"}, "assignee": {"email": "bob@acme.com"}}',
    '2026-01-06T11:00:00Z'
);
