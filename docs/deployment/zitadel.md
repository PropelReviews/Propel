# Zitadel on AWS (ECS) — deploy target & CI/CD

How to run Zitadel alongside Propel in beta/prod. This doc is the **cloud
counterpart** to the local `docker-compose` Zitadel services introduced in the
OIDC auth migration ([PR #28](https://github.com/PropelReviews/Propel/pull/28)).

> **Secrets in this PR / repo defaults:** `ZITADEL_MASTERKEY=MasterkeyNeedsToHave32Characters`,
> `SESSION_SECRET=change-me`, `POSTGRES_PASSWORD=propel`, and the CI `test-secret` /
> `TOKEN_ENCRYPTION_KEY` fixture are **local-dev and test-only demo values**. Beta and
> prod must use Secrets Manager with freshly generated credentials (tables below).

It answers the spec open item: *“Zitadel deploy target for cloud — ECS service
alongside Propel, or its own task?”*

---

## Decision

**Run Zitadel as ECS Fargate tasks in the same cluster and VPC as the Propel
API**, fronted by the **existing shared ALB**, with a dedicated hostname
`auth.<zone>`.

| Option | Verdict | Why |
|--------|---------|-----|
| **Co-located ECS service on shared ALB** | ✅ Recommended | Same VPC/NAT/Aurora; one TLS cert; identical code path to self-host; lowest ops surface |
| Separate ECS cluster for Zitadel | ❌ | Extra NAT, SG wiring, and cert management for no isolation benefit at our scale |
| Zitadel on Aurora in a **separate** RDS cluster | ❌ for V1 | Cost; a second database (`zitadel`) on the existing Aurora cluster is enough |
| Cloudflare Tunnel in front of Zitadel | ⚠️ Defer | ALB already terminates TLS with ACM; tunnels add HTTP/2 quirks Zitadel’s gRPC stack is sensitive to |

**Self-hosted vs cloud:** one Zitadel org locally, one org per customer in
cloud — but the **same container images, env shape, and OIDC redirect URIs**
pattern. No app-code divergence.

---

## Target architecture

```
                         ┌─────────────────────────────────────────┐
  Browser (app.<zone>)   │  Shared ALB (HTTPS, ACM cert)            │
        │                │  ├─ api.<zone>   → propel-api :8000     │
        │  cookie        │  ├─ auth.<zone>  → zitadel-api :8080    │
        └───────────────►│  └─ dagster.<zone> → ingestion :3001   │
                         └─────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
             ECS: propel-api     ECS: zitadel-api    ECS: zitadel-login
             (FastAPI BFF)        (ghcr.io/zitadel)   (ghcr.io/zitadel-login)
                    │                   │                   │
                    │                   └─────────┬─────────┘
                    │                             │
                    ▼                             ▼
             Aurora Serverless v2          DB `zitadel` (same cluster)
             DB `propel`
```

**Login flow in production**

1. User clicks “Sign in” on `https://app.beta.propel.ninja` → browser navigates
   to `https://api.beta.propel.ninja/api/v1/auth/login`.
2. BFF redirects to Zitadel (`https://auth.beta.propel.ninja/...`) — hosted
   login UI v2 (`zitadel-login` container).
3. Zitadel redirects back to
   `https://api.beta.propel.ninja/api/v1/auth/callback` with an auth code.
4. BFF exchanges the code, sets the httpOnly `propel_session` cookie, JIT-
   reconciles user/tenant in Postgres, redirects to the SPA.

**Hostnames (beta example)**

| Host | Service | Port |
|------|---------|------|
| `api.beta.propel.ninja` | Propel API | 8000 |
| `auth.beta.propel.ninja` | Zitadel API + login UI (path-routed) | 8080 / 3000 |
| `app.beta.propel.ninja` | SPA (CloudFront → S3) | — |

Prod mirrors with `propel.ninja`.

---

## ECS services

Two new Fargate services on cluster `propel-{env}` (same as API/Dagster):

| Service | Image | Role |
|---------|-------|------|
| `propel-{env}-zitadel` | `ghcr.io/zitadel/zitadel:{pin}` | IdP API, OIDC, org management |
| `propel-{env}-zitadel-login` | `ghcr.io/zitadel/zitadel-login:{pin}` | Login UI v2 (Next.js) |

**Task sizing (starting point)**

| Container | CPU | Memory | Notes |
|-----------|-----|--------|-------|
| `zitadel-api` | 512 | 1024 | `command: start` after one-time init |
| `zitadel-login` | 256 | 512 | Reads PAT from shared EFS or init sidecar |

Pin the image tag (e.g. `v2.71.10`) — do **not** track `:latest` in prod. See
[Upgrade discipline](#upgrade-discipline) below.

### Init vs runtime (production)

Local compose uses `start-from-init` (init + setup + runtime in one shot).
**In ECS, split the phases** per [Zitadel’s own guidance](https://zitadel.com/docs/self-hosting/manage/updating_scaling):

| Phase | Command | When |
|-------|---------|------|
| Init | `zitadel init` | Once per Aurora cluster lifetime |
| Setup | `zitadel setup --init-projections=true` | Every Zitadel version upgrade |
| Runtime | `zitadel start` | Steady-state ECS service |

Run init/setup as **one-off ECS tasks** (or a `terraform apply` `null_resource`
local-exec against an admin task) before pointing traffic at a new version.
Never roll `zitadel start` until setup completes — projections can take minutes.

### ALB routing

Zitadel’s upstream compose uses Traefik to split:

- `/ui/v2/login/*` → login container
- everything else (incl. `/.well-known/*`, `/oidc/*`) → API container

On ALB, mirror with **host-based rules** on `auth.<zone>`:

```
Priority 200  path /ui/v2/login*  → TG zitadel-login :3000
Priority 100  default             → TG zitadel-api   :8080
```

The API speaks **h2c** internally; ALB → target group uses HTTP (same pattern as
the upstream Traefik `h2c` backend). No gRPC-specific listener is required for
OIDC — only management gRPC if you call the admin API from the BFF later.

**Health checks**

| Target group | Check |
|--------------|-------|
| `zitadel-api` | `CMD` equivalent: `GET /debug/ready` or `zitadel ready` |
| `zitadel-login` | `GET /ui/v2/login/healthy` |

### Database

Reuse the **existing Aurora Serverless v2 cluster** (`propel-{env}-aurora`):

- Propel app → database `propel` (unchanged)
- Zitadel → database `zitadel` (created once via init job or `postgresql` provider)

Zitadel connects with a dedicated DB user (`zitadel_app`) granted on database
`zitadel`. Store the DSN in Secrets Manager
`{name_prefix}/zitadel/database-dsn` — **not** in GitHub.

Do **not** share the `propel` database or the Propel `DATABASE_URL` secret with
Zitadel; table ownership must stay separate.

### Shared bootstrap volume (login PAT)

Login v2 needs a service-user PAT file written during first-instance setup
(`ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH`). Options on ECS:

| Approach | Trade-off |
|----------|-----------|
| **EFS volume** mounted on both tasks | Simplest; matches compose `zitadel-bootstrap` volume |
| Init sidecar in a one-off task → write PAT to Secrets Manager | No EFS; login task reads PAT from SM at start |
| SSM Parameter Store | Same as SM; slightly cheaper for a single string |

Recommend **EFS** for V1 — it mirrors local compose and avoids re-deriving the
PAT on every login task restart.

---

## Secrets & environment variables

### Terraform-generated (never in GitHub)

| Secret | Path | Notes |
|--------|------|-------|
| `ZITADEL_MASTERKEY` | `{prefix}/zitadel/masterkey` | 32+ chars; `random_password` + `ignore_changes` |
| `ZITADEL_DATABASE_POSTGRES_DSN` | `{prefix}/zitadel/database-dsn` | Built from Aurora endpoint + `zitadel` DB |
| `SESSION_SECRET` | `{prefix}/app/SESSION_SECRET` | Replaces `JWT_SECRET`; BFF cookie signing |
| `DATABASE_URL` | `{prefix}/database-url` | Propel app (unchanged) |

### GitHub Environment secrets (per beta/prod)

| Secret | Consumed by |
|--------|-------------|
| `ZITADEL_CLIENT_SECRET` | Propel API (OIDC RP) |
| `ZITADEL_MGMT_TOKEN` | Propel API (org/user provisioning — Phase 1 invites) |

### GitHub Environment variables

| Variable | Example (beta) | Consumed by |
|----------|----------------|-------------|
| `ZITADEL_ISSUER` | `https://auth.beta.propel.ninja` | API (`server_metadata_url` base) |
| `ZITADEL_CLIENT_ID` | `...@project` | API |
| `OAUTH_CALLBACK_BASE_URL` | `https://api.beta.propel.ninja` | API (OIDC redirect URI builder) |
| `FRONTEND_BASE_URL` | `https://app.beta.propel.ninja` | API (post-login redirect) |
| `APP_ENV` | `beta` | API (strict secret validation) |

`CORS_ALLOWED_ORIGINS` continues to be **injected by Terraform** in the stack
module (always includes `https://app.<zone>`).

### Zitadel container env (Terraform task definition)

Key vars (mirror `infrastructure/docker/zitadel-compose.env`):

```hcl
ZITADEL_EXTERNALDOMAIN      = "auth.beta.propel.ninja"
ZITADEL_EXTERNALPORT        = "443"
ZITADEL_EXTERNALSECURE      = "true"
ZITADEL_TLS_ENABLED         = "false"          # TLS at ALB
ZITADEL_DATABASE_POSTGRES_DSN = <from SM>
ZITADEL_MASTERKEY           = <from SM, file or env>
ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED = "true"
ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_BASEURI  = "https://auth.beta.propel.ninja/ui/v2/login/"
# ... DEFAULTLOGINURLV2, DEFAULTLOGOUTURLV2 (see compose)
```

Login container:

```hcl
ZITADEL_API_URL                  = "http://zitadel-api:8080"   # Service Connect or Cloud Map
NEXT_PUBLIC_BASE_PATH            = "/ui/v2/login"
ZITADEL_SERVICE_USER_TOKEN_FILE  = "/zitadel/bootstrap/login-client.pat"
CUSTOM_REQUEST_HEADERS           = "Host:auth.beta.propel.ninja,X-Forwarded-Proto:https"
```

Use **ECS Service Connect** (or Cloud Map) so `zitadel-login` resolves
`zitadel-api` without hard-coding task IPs.

---

## Terraform changes (sketch)

New file: `infrastructure/terraform/modules/api/zitadel.tf` (or a sibling
`modules/zitadel/` if it grows). Follow the **Dagster pattern** in
`ingestion.tf`:

1. ECR repos: `propel-{env}-zitadel`, `propel-{env}-zitadel-login` — or pull
   from `ghcr.io` directly (no ECR mirror) if outbound ghcr.io from private
   subnets is acceptable via NAT.
2. Task definitions for `zitadel` + `zitadel-login`.
3. Target groups + ALB listener rules on `auth_fqdn`.
4. Standalone `aws_security_group_rule` entries (never inline on the ECS SG).
5. Route53 `A` alias `auth.<zone>` → ALB (in `modules/stack/main.tf`).
6. ACM SAN: add `auth_fqdn` to `modules/dns/main.tf`
   `subject_alternative_names`.
7. Secrets Manager resources for masterkey + DSN.
8. Optional EFS for `zitadel-bootstrap`.
9. `random_password` for `SESSION_SECRET`; remove `JWT_SECRET` generation from
   `modules/api/main.tf` once the OIDC BFF ships.

**Propel API task** — extend `local.container_secrets`:

```hcl
container_secrets = concat(
  [{ name = "DATABASE_URL", valueFrom = var.database_url_secret_arn }],
  [{ name = "SESSION_SECRET", valueFrom = aws_secretsmanager_secret.session_secret.arn }],
  [{ name = "ZITADEL_CLIENT_SECRET", valueFrom = aws_secretsmanager_secret.app["ZITADEL_CLIENT_SECRET"].arn }],
  # ...
)
```

Gate with `var.zitadel_enabled` (default `true` once ready) so environments
without auth configured can still plan/apply.

---

## CI/CD — deployment in action

Today’s pipeline ([`cicd.md`](cicd.md)):

```
push main → deploy-beta.yml
  config job   → generate-app-tfvars.json
  deploy job   → terraform apply → deploy-api.sh → deploy-frontend.sh → deploy-landing.sh
```

### Target pipeline (with Zitadel)

```
push main → deploy-beta.yml
  config job
    ├─ generate-app-tfvars.sh        (add ZITADEL_* secrets)
    └─ upload terraform-app-config.json

  deploy job
    ├─ terraform init && apply       (creates/updates Zitadel ECS + secrets + DNS)
    ├─ deploy-zitadel.sh beta        (NEW — see below)
    ├─ deploy-api.sh beta            (API must roll AFTER Zitadel is healthy)
    ├─ deploy-frontend.sh beta
    └─ deploy-landing.sh beta
```

Prod (`deploy-prod.yml`) is identical except account, approval gate, and
`environment:prod` OIDC subject.

### Step-by-step: what happens on `push` to `main`

**1. `config` job** (GitHub Environment `beta`)

- Checks out repo.
- Runs `scripts/generate-app-tfvars.sh` with:
  - `APP_ENVIRONMENT_JSON` = all Environment **variables** (`ZITADEL_ISSUER`,
    `ZITADEL_CLIENT_ID`, `APP_ENV`, `POSTHOG_*`, …)
  - New **secrets** passed explicitly (same pattern as OAuth today):

```yaml
# .github/workflows/deploy-beta.yml (config job env block — additions)
ZITADEL_CLIENT_SECRET: ${{ secrets.ZITADEL_CLIENT_SECRET }}
ZITADEL_MGMT_TOKEN: ${{ secrets.ZITADEL_MGMT_TOKEN }}
```

- Uploads `terraform-app-config.json` artifact.

**2. `deploy` job — OIDC → AWS**

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::536270449640:role/PropelTerraform
```

Short-lived token; no stored AWS keys.

**3. Install Terraform app config**

```bash
cp terraform-app-config.json infrastructure/terraform/environments/beta/app.auto.tfvars.json
```

**4. `terraform apply`**

Creates/updates:

- `auth.beta.propel.ninja` DNS + ACM SAN
- Zitadel ECS services (may be `desired_count = 0` until first image push)
- `SESSION_SECRET`, `ZITADEL_MASTERKEY`, `zitadel` DB DSN in Secrets Manager
- Security group rules for ports 8080 and 3000 from ALB

**5. `scripts/deploy-zitadel.sh beta`** *(new script)*

```bash
#!/usr/bin/env bash
# 1. Resolve pinned image tag from infrastructure/docker/zitadel-compose.env
# 2. If first deploy: run one-off ECS task `zitadel init` + `zitadel setup`
# 3. Force new deployment on propel-beta-zitadel + propel-beta-zitadel-login
# 4. Wait for ALB healthy targets on both TGs
# 5. Smoke: curl -sf https://auth.beta.propel.ninja/.well-known/openid-configuration
```

First-time only: register the Propel OIDC application in Zitadel (redirect URI
`https://api.beta.propel.ninja/api/v1/auth/callback`) — automate via
`scripts/setup-zitadel-oidc.sh` calling the management API with
`ZITADEL_MGMT_TOKEN`, or document a one-time console step.

**6. `scripts/deploy-api.sh beta`** (unchanged flow)

- Build `infrastructure/docker/backend.prod.Dockerfile`
- Push to ECR `propel-beta-api`
- `aws ecs update-service --force-new-deployment` on `propel-beta-api`

API tasks now start with `ZITADEL_ISSUER`, `ZITADEL_CLIENT_ID`,
`ZITADEL_CLIENT_SECRET`, `SESSION_SECRET` injected from Secrets Manager.

**7. `scripts/deploy-frontend.sh beta`**

- `vite build` with `VITE_API_URL=https://api.beta.propel.ninja`
- S3 sync + CloudFront invalidation

No Zitadel secrets in the SPA build — the browser never sees OIDC client
secrets; only the BFF does.

**8. Smoke checks (add to deploy job)**

```bash
curl -sf https://api.beta.propel.ninja/health
curl -sf https://auth.beta.propel.ninja/.well-known/openid-configuration | jq .issuer
# Manual: sign-in flow through app.beta.propel.ninja
```

### `generate-app-tfvars.sh` additions

```bash
# New optional env → app_secrets
--arg zitadel_client_secret "${ZITADEL_CLIENT_SECRET:-}" \
--arg zitadel_mgmt_token "${ZITADEL_MGMT_TOKEN:-}" \
# ...
| if ($zitadel_client_secret | length) > 0 then . + {ZITADEL_CLIENT_SECRET: $zitadel_client_secret} else . end
| if ($zitadel_mgmt_token | length) > 0 then . + {ZITADEL_MGMT_TOKEN: $zitadel_mgmt_token} else . end
```

Non-secret `ZITADEL_ISSUER` and `ZITADEL_CLIENT_ID` ride in `app_environment`
via the existing generic `APP_ENVIRONMENT_JSON` passthrough — no script change
required for those.

### PR / CI checks (`ci.yml`)

No Zitadel container in PR CI today (Postgres service only). Options:

| Approach | When |
|----------|------|
| Keep unit tests on `APP_ENV=test` session bypass | ✅ Already in OIDC PR |
| Add Zitadel as a GitHub Actions service container | Optional integration job; slower |
| Nightly smoke against beta `auth.*` | Post-deploy verification |

---

## Upgrade discipline

Zitadel major upgrades have had **breaking DB migrations**. Treat upgrades as a
runbook, not a rolling deploy:

1. **Pin** image tag in Terraform / `zitadel-compose.env`; bump deliberately.
2. **Backup** Aurora snapshot before any Zitadel version bump.
3. Run `zitadel setup --init-projections=true` as a one-off task; wait for
   completion.
4. Roll `zitadel start` tasks only after setup succeeds.
5. **No downgrades** — restore from snapshot if rollback is needed.
6. Test the bump in **beta**; prod follows after the usual Environment approval.

---

## Self-hosted vs cloud (same code path)

| | Self-hosted (Compose) | Cloud (ECS) |
|---|----------------------|-------------|
| Zitadel orgs | 1 | 1 per customer |
| Database | Postgres `zitadel` DB | Aurora `zitadel` DB |
| Hostname | `localhost:8080` | `auth.<zone>` |
| TLS | Off (local) | ALB + ACM |
| Login UI | `zitadel-login :3002` | `zitadel-login` behind ALB |
| Propel BFF | `backend :8000` | `propel-api` ECS |
| OIDC redirect | `http://localhost:8000/api/v1/auth/callback` | `https://api.<zone>/api/v1/auth/callback` |
| App code | Identical | Identical |

---

## Implementation checklist

Use this when opening the Terraform + CI follow-up PR:

- [ ] `modules/api/zitadel.tf` — ECS services, TGs, listener rules, EFS
- [ ] `modules/dns` — `auth_fqdn` SAN
- [ ] `modules/stack` — Route53 record, `zitadel_enabled` flag
- [ ] `modules/database` or init job — `CREATE DATABASE zitadel`
- [ ] Replace `JWT_SECRET` → `SESSION_SECRET` in Terraform + API module
- [ ] `scripts/deploy-zitadel.sh`
- [ ] `deploy-beta.yml` / `deploy-prod.yml` — Zitadel secrets + deploy step
- [ ] `generate-app-tfvars.sh` — Zitadel secret mapping
- [ ] GitHub Environment vars/secrets on `beta` and `prod`
- [ ] Register OIDC app in Zitadel (redirect URI, scopes)
- [ ] Bootstrap runbook update in `deployment/bootstrap.md`
- [ ] Remove stale `JWT_SECRET` / `AUTH_REGISTRATION_ENABLED` references in
      `infrastructure/terraform/README.md`

---

## Related docs

- [CI/CD overview](cicd.md)
- [Terraform architecture](../../infrastructure/terraform/README.md)
- [AWS bootstrap runbook](bootstrap.md)
- [Self-hosting (Compose Zitadel)](../self-hosting.md)
- Auth spec & Phase 1 BFF — [PR #28](https://github.com/PropelReviews/Propel/pull/28)
