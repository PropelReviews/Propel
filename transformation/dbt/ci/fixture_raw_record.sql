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
    '{"node_id": "PR_1", "number": 1, "state": "closed",
      "created_at": "2026-01-05T10:00:00Z", "closed_at": "2026-01-05T11:00:00Z",
      "merged_at": null, "user": {"login": "alice"}, "org": "acme", "repo": "api"}',
    '2026-01-05T12:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_1',
    '{"node_id": "PR_1", "number": 1, "state": "open",
      "created_at": "2026-01-05T10:00:00Z", "closed_at": null,
      "merged_at": null, "user": {"login": "alice"}, "org": "acme", "repo": "api"}',
    '2026-01-06T12:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_2',
    '{"node_id": "PR_2", "number": 2, "state": "closed",
      "created_at": "2026-01-05T09:00:00Z", "closed_at": "2026-01-06T09:00:00Z",
      "merged_at": "2026-01-06T09:00:00Z", "user": {"login": "bob"}, "org": "acme", "repo": "api"}',
    '2026-01-06T10:00:00Z'
),
(
    'aaaaaaaa-0000-0000-0000-000000000001', 'github', 'pull_requests', 'PR_3',
    '{"node_id": "PR_3", "number": 3, "state": "closed",
      "created_at": "2026-01-06T08:00:00Z", "closed_at": "2026-01-07T08:00:00Z",
      "merged_at": null, "user": {"login": "carol"}, "org": "acme", "repo": "web"}',
    '2026-01-07T09:00:00Z'
);
