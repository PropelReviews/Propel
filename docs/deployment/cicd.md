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

1. **Checkout** the repo.
2. **Configure AWS credentials (OIDC)** — assume `PropelTerraform` in the target
   account.
3. **Forward Actions variables to env** — every `vars.*` becomes a shell env var
   (consumed by the SPA build, e.g. `VITE_*`, `POSTHOG_*`).
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

- **`beta` and `prod` Environments** (Settings → Environments). Each job binds
  its environment so environment-scoped Actions **variables** (e.g.
  `POSTHOG_TOKEN`, `POSTHOG_HOST`) flow into `vars` and reach both the API
  container and the SPA build. Repository/org-level variables still work as a
  fallback when an environment does not override them.
- **`prod` Environment** — add required reviewers to gate prod deploys.
- Per-account OIDC provider + `PropelTerraform` role (bootstrap Step 4).
