# Propel backend data model

Canonical reference for entity relationships in the Propel API database. The v1 schema covers **users, login OAuth, tenants, memberships, and invites**. The ingestion layer (migration `002`) adds **`connected_accounts`, `raw_record`, `datapoint`, and `ingestion_run`** for landing external data (see [ingestion overview](#ingestion-entities-migration-002)).

## v1 entities

| Entity | Table | Description |
|---|---|---|
| User | `users` | A person with a Propel account (email/password and/or login OAuth) |
| OAuthAccount | `oauth_accounts` | Login provider link (Google, GitHub) — identity only, not tool tokens |
| Tenant | `tenants` | An onboarded organization |
| TenantMembership | `tenant_memberships` | Join table: which users belong to which tenants and their role |
| TenantInvite | `tenant_invites` | Pending invitation to join a tenant |

## v1 ER diagram

```mermaid
erDiagram
    users ||--o{ oauth_accounts : has
    users ||--o{ tenant_memberships : has
    tenants ||--o{ tenant_memberships : has
    tenants ||--o{ tenant_invites : has
    users ||--o{ tenant_invites : invited_by

    users {
        uuid id PK
        string email UK
        string hashed_password
        string name
        bool is_active
        bool is_verified
        timestamp created_at
    }

    oauth_accounts {
        uuid id PK
        uuid user_id FK
        string oauth_name
        string account_id
        string account_email
    }

    tenants {
        uuid id PK
        string name
        string slug UK
        timestamp deleted_at
        timestamp created_at
    }

    tenant_memberships {
        uuid id PK
        uuid tenant_id FK
        uuid user_id FK
        enum role
        timestamp created_at
    }

    tenant_invites {
        uuid id PK
        uuid tenant_id FK
        string email
        enum role
        string token_hash
        uuid invited_by_user_id FK
        timestamp expires_at
        timestamp accepted_at
    }
```

## Relationship rules

| Relationship | Cardinality | Notes |
|---|---|---|
| User → OAuthAccount | 1:N | One user can link multiple login providers; unique on `(oauth_name, account_id)` |
| User ↔ Tenant | M:N via `tenant_memberships` | A user can belong to multiple tenants; a tenant has many users |
| Tenant → TenantMembership | 1:N | Membership is the source of truth for tenant access |
| User → TenantMembership | 1:N | Role (`admin`, `manager`, `individual`) lives on the membership, not the user |
| Tenant → TenantInvite | 1:N | Invites are tenant-scoped; unique pending invite per `(tenant_id, email)` |
| User → TenantInvite (invited_by) | 1:N | Audit trail; nullable FK with `ON DELETE SET NULL` |

## Integrity rules

- **`tenant_memberships`**: unique `(tenant_id, user_id)` — one role per user per tenant
- **`tenants.slug`**: globally unique; used in URLs; API returns `409` on conflict
- **`tenants.deleted_at`**: soft delete; memberships remain but tenant is hidden from listings
- **`tenant_invites.token_hash`**: unique; raw token never stored (SHA-256 hash only)
- **Last-admin guard**: application logic prevents removing or demoting the sole admin (not a DB constraint)

## Roles and permissions

| Action | Admin | Manager | Individual |
|---|---|---|---|
| Create tenant (becomes admin) | yes | yes | yes |
| Update / delete tenant | yes | no | no |
| List / view members | yes | yes | yes |
| Invite **admin** | yes | no | no |
| Invite **manager** or **individual** | yes | yes | no |
| Assign / change roles | yes | no | no |
| Remove members | yes | no | no |

Enforced in `backend/app/auth/permissions.py` and FastAPI dependencies.

## Login OAuth vs tool connections

| Concern | Table (v1) | Purpose |
|---|---|---|
| **Sign-in** | `oauth_accounts` | Authenticate the Propel user via Google/GitHub |
| **Tool connections** | `connected_accounts` (v2) | Authorize Propel to read/write third-party accounts on behalf of a tenant |

Signing in with GitHub does **not** automatically connect the tenant's GitHub org. Those are separate user actions with different OAuth apps/scopes. Tenant tool connections live in `connected_accounts` (below), and for GitHub specifically a tenant admin installs the **GitHub App** (not the login OAuth app) via `/api/v1/tenants/{tenant_id}/connections/github/install`.

## Ingestion entities (migration `002`)

V1 ingestion is **landing only**: Meltano (`tap-github` → custom `target-propel`) pulls provider data and writes it to Postgres. No transforms run at ingest — that is a later dbt layer. See the [backend README](../../backend/README.md#ingestion-v1--landing-only) for how runs are driven.

| Entity | Table | Description |
|---|---|---|
| ConnectedAccount | `connected_accounts` | A tenant's link to a source. GitHub App installs use `auth_type='github_app_installation'`; future OAuth tools use `auth_type='oauth'` with encrypted tokens. |
| RawRecord | `raw_record` | Append-only landing of the provider payload exactly as fetched (audit + replay + lineage). |
| Datapoint | `datapoint` | Normalized, source-agnostic envelope (who/when/what + pointer to `raw_record`). Generic at ingest; provider detail stays in `raw_record.payload` and a passthrough `metadata`. |
| IngestionRun | `ingestion_run` | One row per `(connected_account, resource_type)` run: counts, status, error, and incremental `cursor`. |

```mermaid
erDiagram
    tenants ||--o{ connected_accounts : owns
    users ||--o{ connected_accounts : connected_by
    connected_accounts ||--o{ ingestion_run : runs
    ingestion_run ||--o{ raw_record : produces
    raw_record ||--o| datapoint : lineage

    connected_accounts {
        uuid id PK
        uuid tenant_id FK
        uuid connected_by_user_id FK
        string provider
        string auth_type
        string external_account_id
        string external_account_name
        text access_token_encrypted
        text refresh_token_encrypted
        timestamp token_expires_at
        jsonb scopes
        string status
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }

    raw_record {
        uuid id PK
        uuid tenant_id
        string source
        string resource_type
        string source_id
        jsonb payload
        timestamp fetched_at
        uuid run_id
    }

    datapoint {
        uuid id PK
        uuid tenant_id
        string source
        string tool
        string kind
        string name
        string subject_type
        string subject_id
        timestamp occurred_at
        timestamp period_start
        timestamp period_end
        timestamp observed_at
        string source_key
        jsonb metadata
        uuid raw_record_id
        timestamp created_at
    }

    ingestion_run {
        uuid id PK
        uuid tenant_id
        uuid connected_account_id FK
        string source
        string resource_type
        timestamp started_at
        timestamp finished_at
        string status
        int records_pulled
        int datapoints_written
        jsonb cursor
        text error
    }
```

`provider`, `auth_type`, `status`, `kind`, etc. are stored as **text** (not Postgres enums) so new sources and resource types land without a migration. The matching `StrEnum`s for app-level use live in `backend/app/models/enums.py` (`IntegrationProvider`, `AuthType`, `ConnectionStatus`, `DatapointKind`, `IngestionRunStatus`).

### Ingestion integrity rules

- **`connected_accounts`**: unique `(tenant_id, provider, external_account_id)`. GitHub App installs store the `installation_id` in `external_account_id`; tokens are minted per run and never persisted for app installs.
- **`datapoint` events**: partial unique index `datapoint_event_uq (tenant_id, source, source_key) where kind='event'`. Re-fetching an event is a no-op (`ON CONFLICT DO NOTHING`).
- **`datapoint` measurements**: partial unique index `datapoint_measure_uq (tenant_id, tool, name, subject_id, period_start) where kind='measurement'`. Restatements upsert, but only when the incoming `observed_at` is newer (newest-wins) — this is what prevents double-counting when a provider republishes a period.
- **`raw_record`**: never deduped or updated; dedup/restatement is resolved only at the `datapoint` layer.

## Related docs

- [Backend README](../../backend/README.md) — API endpoints and local setup
- [Backend service](../backend/README.md) — FastAPI application
