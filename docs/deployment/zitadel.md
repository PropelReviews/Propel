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
| `scripts/deploy-zitadel.sh <beta\|prod>` | CI | Resolves the IAM_OWNER PAT, runs the bootstrap, and publishes the OIDC client id/secret into that environment's Secrets Manager. Re-deploys are idempotent: existing SM credentials are passed into the bootstrap so an already-created OIDC app can be reused; if the app exists but SM still has placeholders, the bootstrap regenerates the client secret and publishes it. |
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
2. Retrieve that PAT once via ECS Exec and store it. The `zitadel` API image is
   distroless (no shell), so exec into the `zitadel-login` container, which ships
   a shell and mounts the same `/zitadel/bootstrap` EFS volume:

   ```bash
   CLUSTER=$(terraform -chdir=infrastructure/terraform/environments/prod output -raw ecs_cluster_name)
   TASK=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name propel-prod-zitadel-login \
            --query 'taskArns[0]' --output text)
   aws ecs execute-command --cluster "$CLUSTER" --task "$TASK" --container zitadel-login \
            --interactive --command "cat /zitadel/bootstrap/admin.pat"
   # store it:
   aws secretsmanager put-secret-value --secret-id propel-prod/zitadel/MGMT_TOKEN --secret-string '<PAT>'
   ```

   `scripts/deploy-zitadel.sh` automates this same read (via
   `scripts/lib/zitadel-pat.sh`) on subsequent deploys.

   Also set it as the `ZITADEL_MGMT_TOKEN` GitHub environment secret on both
   `beta` and `prod`. Each deploy's `config` job reads that environment secret and
   lifts it into the `zitadel_mgmt_token` Terraform variable, which Terraform seeds
   into the env's `…/zitadel/MGMT_TOKEN` secret — so no manual SM sync is needed.
   (This indirection matters for beta: its `deploy` job stays on the
   `refs/heads/main` OIDC subject and cannot read environment secrets directly.)
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

**Login V2 + GitHub:** GitHub does not return separate first/last names, so Login
V2 auto-creation fails without an Actions V2 response hook. The bootstrap
registers `propelGitHubIdpMapping` pointing at
`https://api.<env>.propel.ninja/api/v1/zitadel/actions/idp-intent` and stores
the signing key in `<prefix>/zitadel/ACTIONS_SIGNING_KEY` for the API task.

**One GitHub IdP, always:** every bootstrap run purges *all* existing GitHub IdPs
(login-policy detach + delete via the admin API) and recreates exactly one. This
replaces the older keep-one-and-dedupe approach, which could leave duplicates
behind when a delete silently failed — the cause of multiple GitHub buttons and
the broken hosted login. All instance IdP calls use the admin API only (the
org-scoped management API could miss instance IdPs and create yet another).

## Management console & super-admin

The console ships at `https://auth.propel.ninja/ui/console`. The bootstrap grants
`IAM_OWNER` to the `ZITADEL_ADMIN_EMAIL` human user. If that user does not yet
exist it is created with a verified email **and an initial password** (from
`ZITADEL_ADMIN_PASSWORD`, or generated and printed once), so the console is
reachable with username/password even when the GitHub IdP is unavailable. The
admin can still sign in via GitHub (auto-linked by email). Re-runs are idempotent.

Set `ZITADEL_ADMIN_PASSWORD` as a prod GitHub environment secret to keep the
password stable across deploys; otherwise a fresh one is generated only when the
user is first created.

## Strict mode (prod)

`zitadel_bootstrap.py --strict` (auto-enabled for `--env prod`, and passed by
`deploy-zitadel.sh prod`) turns instance-level config failures — GitHub IdP,
Actions V2 hook, login branding, and the super-admin grant — into hard errors
instead of warnings. A prod deploy now fails loudly rather than silently shipping
broken auth. Local and beta keep the historical best-effort behaviour.

## Recovery

Two operator scripts, lightest first:

| Script | Touches DB? | Use when |
|--------|-------------|----------|
| `scripts/zitadel-repair-instance.sh prod` | No | Instance config is wrong (e.g. duplicate GitHub IdPs, missing super-admin). Re-runs the bootstrap in `--strict`, purging + recreating the GitHub IdP and re-granting the admin. Reuses the existing OIDC app creds so the client secret is not rotated. |
| `scripts/reset-zitadel-cloud.sh prod` | **Yes — drops `zitadel`** | First-boot chicken-and-egg, or a corrupt instance with no customer orgs worth keeping. Drops the DB, restarts ECS to re-seed the EFS PATs, copies the new IAM_OWNER PAT into `propel-prod/zitadel/MGMT_TOKEN`. |

**Full prod reset (no customer orgs to preserve):**

```bash
scripts/reset-zitadel-cloud.sh prod
# Copy the new PAT it prints into the ZITADEL_MGMT_TOKEN GitHub env secret, then:
scripts/deploy-zitadel.sh prod && scripts/deploy-api.sh prod
```

Before redeploying, confirm the prod GitHub environment has `ZITADEL_ADMIN_EMAIL`
(and ideally `ZITADEL_ADMIN_PASSWORD`) set, and that the GitHub App's
Authorization callback URLs include
`https://auth.propel.ninja/ui/login/login/externalidp/callback`.

After recovery, verify: the hosted Login UI shows a **single** GitHub button,
console login works via both email/password and GitHub, and
`POST /api/v1/zitadel/actions/idp-intent` returns 200 (not 503) once the Actions
signing key is in Secrets Manager.

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
