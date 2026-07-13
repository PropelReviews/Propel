# CI/CD

GitHub Actions runs all checks and deploys. AWS auth is via **OIDC** — no stored
AWS keys (see [`bootstrap.md`](bootstrap.md) Step 4).

## Status badges

| Check | Badge |
|-------|-------|
| CI | [![CI](https://github.com/PropelReviews/Propel/actions/workflows/ci.yml/badge.svg)](https://github.com/PropelReviews/Propel/actions/workflows/ci.yml) |
| Deploy Prod | [![Deploy Prod](https://github.com/PropelReviews/Propel/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/PropelReviews/Propel/actions/workflows/deploy-prod.yml) |
| Rollback Prod | [![Rollback Prod](https://github.com/PropelReviews/Propel/actions/workflows/rollback-prod.yml/badge.svg)](https://github.com/PropelReviews/Propel/actions/workflows/rollback-prod.yml) |

Live deployment history (SHA, actor, URL) is on the repo **Environments → prod**
page. Each deploy job sets `environment.url` to `https://propel.ninja`.

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| [`ci.yml`](../../.github/workflows/ci.yml) | PR, push to `main` | Terraform `fmt -check` + `validate` (prod); backend Ruff lint/format + `pytest`; ingestion integration; dbt; frontend ESLint + Prettier + TypeScript + `vitest` + Vite builds |
| [`deploy-prod.yml`](../../.github/workflows/deploy-prod.yml) | CI success on `main`, push `v*` tag, manual | OIDC → prod role → `terraform apply` → deploy API / frontend / landing (uses the `prod` Environment for vars + approval) |
| [`rollback-prod.yml`](../../.github/workflows/rollback-prod.yml) | manual | Restore a previous git SHA (ECR image + S3 release archives); no Terraform apply |

> **Note:** Beta was decommissioned in June 2026. The `deploy-beta.yml` workflow
> has been removed. Prod auto-deploys when CI passes on `main`.

## Deploy flow

1. **Merge to `main`** — `ci.yml` runs. On success, `deploy-prod.yml` starts via
   `workflow_run` (or push a `v*` tag / run **Deploy Prod** manually).
2. **`prepare` job** — resolves the commit SHA (the CI head SHA on
   `workflow_run`, otherwise the pushed/dispatch ref).
3. **`config` job** — binds the `prod` GitHub Environment so environment-scoped
   Actions variables and secrets are available (and prod approval runs here). This
   job does **not** call AWS. It runs
   [`scripts/generate-app-tfvars.sh`](../../scripts/generate-app-tfvars.sh) to
   build `app.auto.tfvars.json` (variables → `app_environment`, secrets →
   `app_secrets`) and uploads it as a workflow artifact.
4. **`deploy` job** — checks out that SHA, downloads the Terraform config
   artifact, and assumes `PropelTerraform` via OIDC. The deploy job binds the
   `prod` Environment so the OIDC subject is `environment:prod` (matches
   `prod-trust.json`); approval runs on the `config` job.
5. **Forward Actions variables to env** — vars from the `config` job become shell
   env vars (consumed by the SPA build, e.g. `VITE_*`, `POSTHOG_*`).
6. **Install Terraform app config** — the artifact from `config` is copied to
   `app.auto.tfvars.json` in the prod Terraform directory.
7. **`terraform init` + `apply`**
8. **Build, push & deploy API** — `scripts/deploy-api.sh prod` builds
   `backend.prod.Dockerfile`, pushes ECR tags `$SHA` and `latest`, rolls ECS
   services onto the SHA image, and waits until services are stable.
9. **Build & publish frontend / landing** — sync to S3 live roots **and** archive
   under `s3://…/releases/$SHA/` for rollbacks, then invalidate CloudFront.
10. **Smoke check** — `GET https://api.propel.ninja/health`.

Every release is identified by the full git SHA (ECR image tag + S3 archive key).

## Adding app config

Add a GitHub Actions **variable** (org or repo level, scoped per environment).
It flows to both the API container and the SPA build with no code changes.

Add a GitHub Actions **secret** on the `prod` environment for OAuth client
secrets when those providers are enabled:

| Secret | Required | Consumed by |
|--------|----------|-------------|
| `OAUTH_GOOGLE_CLIENT_SECRET` | Optional | API |
| `OAUTH_GITHUB_CLIENT_SECRET` | Optional | API |
| `OAUTH_LINEAR_CLIENT_SECRET` | Optional | API (Linear data connection) |
| `TOKEN_ENCRYPTION_KEY` | When Linear is enabled | API (encrypts stored OAuth tokens) |

`JWT_SECRET` is **not** configured in GitHub — Terraform generates it on first
apply and stores it in AWS Secrets Manager (64 characters, unique per
environment/account). Set the `APP_ENV` variable to `production` on prod so the
API validates configuration at startup.

## Releasing to prod

**Default path:** merge to `main`. After CI is green, Deploy Prod runs
automatically (approve in the `prod` Environment if reviewers are configured).

Cut a versioned release tag (also deploys):

```bash
git tag v1.2.3
git push origin v1.2.3      # triggers deploy-prod.yml; approve in the Environment
```

Or trigger **Deploy Prod** manually from the Actions tab (`workflow_dispatch`),
optionally with a specific ref.

## Rollback

Rollbacks restore a **previous successful deploy SHA** without re-running
Terraform:

1. Find the SHA on **Environments → prod**, the Deploy Prod run summary, or:

   ```bash
   AWS_PROFILE=propel-prod ./scripts/rollback.sh prod --list
   ```

2. From Actions → **Rollback Prod**, enter the full SHA and type `rollback`, then
   approve the `prod` Environment gate.

   Or locally:

   ```bash
   AWS_PROFILE=propel-prod ./scripts/rollback.sh prod <full-git-sha>
   ```

What rollback does:

- Points API / ingestion / Dask ECS services at the ECR image tagged with that SHA
- Restores frontend + landing from `s3://…/releases/<sha>/` and invalidates CloudFront
- Smoke-checks `/health`

What it does **not** do:

- Change Terraform-managed infra or Secrets Manager values
- Reverse database migrations — use expand/contract migrations so older code
  stays compatible with the current schema

Release archives and ECR SHA tags are retained for about **30 days** (S3
lifecycle + ECR lifecycle policy).

## Required GitHub config

- **`prod` Environment** (Settings → Environments). The `config` job binds the
  environment so environment-scoped Actions **variables** (e.g. `APP_ENV`,
  `POSTHOG_TOKEN`, `POSTHOG_HOST`) and **secrets** (OAuth client secrets when
  enabled) reach the API via Terraform.
- **`prod` Environment** — add required reviewers to gate prod deploys (runs on
  the `config` job). Deployment status and the live URL appear on this page.
- Prod OIDC provider + `PropelTerraform` role (bootstrap Step 4). If prod OIDC
  fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`, re-apply
  `prod-trust.json` (see bootstrap troubleshooting).
