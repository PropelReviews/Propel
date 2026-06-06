# CI/CD

GitHub Actions runs all checks and deploys. AWS auth is via **OIDC** — no stored
AWS keys (see [`bootstrap.md`](bootstrap.md) Step 4).

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| [`ci.yml`](../../.github/workflows/ci.yml) | PR, push to `main` | `terraform fmt -check` + `validate` (beta & prod), backend `pytest`, frontend `vitest` |
| [`deploy-beta.yml`](../../.github/workflows/deploy-beta.yml) | push to `main`, manual | OIDC → beta role → `terraform apply` → deploy API → deploy frontend (uses the `beta` Environment for vars) |
| [`deploy-prod.yml`](../../.github/workflows/deploy-prod.yml) | successful beta deploy on `main`, push `v*` tag, manual | Same as beta, in prod, gated by the `prod` Environment approval |

## Deploy flow (beta and prod are identical except account/trigger)

1. **`config` job** — binds the `beta` / `prod` GitHub Environment so
   environment-scoped Actions variables are available (and prod approval runs
   here). This job does **not** call AWS.
2. **`deploy` job** — checks out the repo and assumes `PropelTerraform` via OIDC.
   **Beta** uses the `refs/heads/main` subject (deploy job has no Environment).
   **Prod** binds the `prod` Environment on the deploy job so the OIDC subject is
   `environment:prod` (matches `prod-trust.json`); approval still runs only on
   the `config` job.
3. **Forward Actions variables to env** — vars from the `config` job become shell
   env vars (consumed by the SPA build, e.g. `VITE_*`, `POSTHOG_*`).
4. **Generate app config** — `{"app_environment": <all vars>}` is written to
   `app.auto.tfvars.json`, auto-loaded by Terraform → becomes the API
   container's environment.
5. **`terraform init` + `apply`** — prod additionally assumes the beta role to
   write the `beta.propel.ninja` NS delegation.
6. **Build, push & deploy API** — `scripts/deploy-api.sh <env>` builds
   `backend.prod.Dockerfile`, pushes to ECR, forces an ECS redeploy.
7. **Build & publish frontend** — `scripts/deploy-frontend.sh <env>` runs
   `vite build`, syncs to S3, invalidates CloudFront.

## Adding app config

Add a GitHub Actions **variable** (org or repo level). It flows to both the API
container and the SPA build with no code changes. Use the Terraform `app_secrets`
map for values that must not be exposed (they become Secrets Manager secrets).

## Releasing to prod

Every successful **Deploy Beta** run on `main` automatically triggers **Deploy
Prod** (still gated by the `prod` Environment approval if reviewers are
configured). You can also cut a versioned release:

```bash
git tag v1.2.3
git push origin v1.2.3      # triggers deploy-prod.yml; approve in the Environment
```

## Required GitHub config

- **`beta` and `prod` Environments** (Settings → Environments). The `config` job
  binds each environment so environment-scoped Actions **variables** (e.g.
  `POSTHOG_TOKEN`, `POSTHOG_HOST`) reach both the API container and the SPA
  build. Repository/org-level variables still work as a fallback.
- **`prod` Environment** — add required reviewers to gate prod deploys (runs on
  the `config` job).
- Per-account OIDC provider + `PropelTerraform` role (bootstrap Step 4). If prod
  OIDC fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`,
  re-apply `infrastructure/terraform/bootstrap/prod-trust.json` to the prod role
  (the GitHub Environment was renamed `production` → `prod`; stale IAM trust
  policies still reference `environment:production`).
