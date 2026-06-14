# Zitadel — identity for Propel (runbook)

Propel uses [Zitadel](https://zitadel.com) as its OIDC identity provider. This is
the implemented runbook: one shared instance, environments as projects, and
customers as organizations (Model B).

- **Local:** `docker compose` runs Zitadel + the Login UI v2; bootstrap is
  automatic.
- **Cloud:** a **single** Zitadel instance is hosted in **prod** at
  `auth.propel.ninja`. Beta has no Zitadel of its own — it consumes the prod
  instance.

## Architecture

```
            ┌──────────────────────────────────────────────┐
            │  ONE Zitadel instance  (prod: auth.propel.ninja)
            │  org "Propel"  (the company)                  │
            │   ├─ project "Propel Prod"  → OIDC app (prod API)
            │   ├─ project "Propel Beta"  → OIDC app (beta API)
            │   └─ instance: GitHub IdP, login branding, super-admin
            │  org "Acme Corp"  (a customer)  ── grant ─▶ Propel Prod
            │  org "Globex"     (a customer)  ── grant ─▶ Propel Prod
            └──────────────────────────────────────────────┘
                     ▲                         ▲
         prod API (app.propel.ninja)   beta API (app.beta.propel.ninja)
         consumes "Propel Prod" app    consumes "Propel Beta" app
         (creds in prod SM)            (creds in beta SM, cross-account)
```

Why one instance: customers are real and live only in prod; beta is internal
staging for the app. One console, one place to onboard customers, lower ops.
Trade-offs: beta authenticates against prod over the internet, beta's OIDC client
secret is provisioned in the beta account, and Zitadel-the-software upgrades are
tested locally (not in a separate cloud beta). See the original decision in chat
history if revisiting.

### Multi-tenancy: Model B

Each **customer = a Zitadel organization**, granted access to the per-environment
Propel **project**. A user's OIDC token carries their org
(`urn:zitadel:iam:org:id`) and granted project roles
(`urn:zitadel:iam:org:project:roles`). On login the API
(`backend/app/auth/reconcile.py`) mirrors that org into a Propel `Tenant` and the
role into a `TenantMembership`. The project has **"Only authorized users can
authenticate"** on, so a user must hold a project role to log in at all.

Project role → Propel role mapping lives in `reconcile._ROLE_MAP`
(`owner`/`admin`/`manager`/`member`). The first user of a new org-tenant always
becomes its `owner`.

## Login flow

1. User clicks "Sign in" on `app.<env>.propel.ninja` → `api.<env>…/api/v1/auth/login`.
2. The BFF redirects to the shared Zitadel (`https://auth.propel.ninja/...`,
   Login UI v2) — GitHub or username/password.
3. Zitadel redirects back to `https://api.<env>…/api/v1/auth/callback` with a code.
4. The BFF exchanges the code, sets the httpOnly `propel_session` cookie,
   JIT-reconciles user + tenant + role in Postgres, and redirects to the SPA.

## The three scripts

| Script | Runs where | Does |
|--------|-----------|------|
| `scripts/zitadel_bootstrap.py` | local + CI | Ensures the per-env **project** (roles + "only authorized users") and its **OIDC app**; for the instance-owning env (local/prod) also configures the **GitHub IdP**, **login branding**, and the **human super-admin**. `--emit-json` writes the minted client creds for the deploy script. |
| `scripts/deploy-zitadel.sh <beta\|prod>` | CI | Resolves the IAM_OWNER PAT, runs the bootstrap, and publishes the OIDC client id/secret into that environment's Secrets Manager. |
| `scripts/onboard-org.py` | operator | Creates a customer **org + first admin**, **grants** them the Propel project, and assigns the admin the `owner` role. |

`local`/`beta`/`prod` map to projects `Propel Local`/`Propel Beta`/`Propel Prod`
(`PROJECT_NAMES` in `zitadel_bootstrap.py`). Instance-level config is owned by
`INSTANCE_OWNER_ENVS = {local, prod}`; beta never touches the IdP/branding/admin.

## Local development

`docker compose up` runs the `zitadel-oidc-init` one-shot after Zitadel + Login
UI are healthy. It creates the `Propel Local` project + OIDC app and writes
`ZITADEL_CLIENT_ID/SECRET` and `SESSION_SECRET` to `.env`. To set the local
super-admin, export `ZITADEL_ADMIN_EMAIL` before bootstrapping.

```bash
./scripts/setup-zitadel-oidc.sh          # idempotent
ZITADEL_ADMIN_EMAIL=you@propel.test ./scripts/setup-zitadel-oidc.sh --force
docker compose restart backend
```

## Cloud topology in Terraform

Two independent flags on the stack/api modules:

- `zitadel_enabled` — **host** the instance (ECS + Login UI + EFS + `auth.<zone>`
  ALB rules/DNS/ACM SAN). `true` only in **prod**.
- `zitadel_issuer_url` — the public issuer the API **consumes**. Prod = its own
  `https://auth.propel.ninja`; beta = the same prod URL (cross-account).

The OIDC client id/secret are Secrets Manager placeholders
(`<prefix>/app/ZITADEL_CLIENT_ID|SECRET`, `ignore_changes`) created in **every**
consuming environment and overwritten by the bootstrap. Beta additionally gets
`<prefix>/zitadel/MGMT_TOKEN` (the prod PAT it needs to register its app).

## CI/CD

`deploy-prod.yml` / `deploy-beta.yml` (after `terraform apply`, before
`deploy-api.sh`), gated on the `ZITADEL_ENABLED` Actions variable:

```
terraform apply
  → deploy-zitadel.sh <env>     # bootstrap project/app, publish client creds to SM
  → deploy-api.sh <env>         # rolls the API onto the new secrets
```

- **prod** step passes `ZITADEL_MGMT_TOKEN`, `GITHUB_APP_CLIENT_ID/SECRET`, and
  `ZITADEL_ADMIN_EMAIL` (instance-level config).
- **beta** step passes only `ZITADEL_MGMT_TOKEN` (the prod PAT).

## First-time bootstrap (prod)

1. Set `TF_VAR_zitadel_enabled=true` (or the `zitadel_enabled` tfvar) and run
   `terraform apply` for prod. This stands up the instance; on first boot Zitadel
   writes an IAM_OWNER PAT to the EFS bootstrap volume.
2. Retrieve that PAT once via ECS Exec (the Zitadel service has
   `enable_execute_command = true`) and store it:

   ```bash
   CLUSTER=$(terraform -chdir=infrastructure/terraform/environments/prod output -raw ecs_cluster_name)
   TASK=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name propel-prod-zitadel \
            --query 'taskArns[0]' --output text)
   aws ecs execute-command --cluster "$CLUSTER" --task "$TASK" --container zitadel \
            --interactive --command "cat /zitadel/bootstrap/admin.pat"
   # store it:
   aws secretsmanager put-secret-value --secret-id propel-prod/zitadel/MGMT_TOKEN --secret-string '<PAT>'
   ```

   Also set it as the `ZITADEL_MGMT_TOKEN` GitHub environment secret for both
   `beta` and `prod`, and sync it into beta's SM
   (`propel-beta/zitadel/MGMT_TOKEN`) so beta can register its app.
3. Set the `ZITADEL_ENABLED=true` Actions variable on both environments. The next
   deploy runs `deploy-zitadel.sh`.

## GitHub App callback URLs (one-time)

The login GitHub IdP uses the existing Propel GitHub App's OAuth credentials.
Add Zitadel's IdP callback to the GitHub App's **Authorization callback URLs**:

```
https://auth.propel.ninja/ui/login/login/externalidp/callback
```

(Local dev: `http://localhost:8080/ui/login/login/externalidp/callback`.) The
per-environment Propel BFF redirect URIs
(`https://api.<env>.propel.ninja/api/v1/auth/callback`) are registered
automatically on each project's OIDC app by the bootstrap — no manual step.

## Management console & super-admin

The console ships at `https://auth.propel.ninja/ui/console`. The bootstrap grants
`IAM_OWNER` to the `ZITADEL_ADMIN_EMAIL` human user (created if missing; signs in
via GitHub SSO by matching email, or an init mail). Re-runs are idempotent.

## Onboarding a customer

```bash
ZITADEL_MGMT_TOKEN=<prod PAT> ZITADEL_ISSUER=https://auth.propel.ninja \
  scripts/onboard-org.py --env prod \
    --org "Acme Corp" --admin-email admin@acme.com --admin-name "Ada Lovelace"
```

This creates the org, an ORG_OWNER admin, a project grant to `Propel Prod`, and
assigns the admin the `owner` project role (prints an initial password unless
`--admin-password` is given). The admin can then invite teammates and assign
roles from their own console, and (optionally) configure their own SSO IdP.

## Upgrade discipline

Zitadel major upgrades can have breaking DB migrations. Pin the image tag
(`zitadel_image` / `zitadel_login_image`), snapshot Aurora before a bump, test
the bump **locally**, then apply to the single prod instance during a window.
No downgrades — restore from snapshot to roll back.

## Related docs

- [CI/CD overview](cicd.md)
- [AWS bootstrap runbook](bootstrap.md)
- [Terraform architecture](../../infrastructure/terraform/README.md)
- [Self-hosting (Compose Zitadel)](../self-hosting.md)
