# CI/CD

GitHub Actions runs all checks and deploys. AWS auth is via **OIDC** — no stored
AWS keys (see [`bootstrap.md`](bootstrap.md) Step 4).

## Workflows

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| [`ci.yml`](../../.github/workflows/ci.yml) | PR, push to `main` | Terraform `fmt -check` + `validate` (prod); backend Ruff lint/format + `pytest`; frontend ESLint + Prettier + TypeScript + `vitest` + Vite builds |
| [`deploy-prod.yml`](../../.github/workflows/deploy-prod.yml) | push `v*` tag, manual | OIDC → prod role → `terraform apply` → deploy API → deploy frontend (uses the `prod` Environment for vars + approval) |

> **Note:** Beta was decommissioned in June 2026. The `deploy-beta.yml` workflow
> has been removed. Prod deploys via version tags or manual dispatch only.

## Deploy flow

1. **`config` job** — binds the `prod` GitHub Environment so environment-scoped
   Actions variables and secrets are available (and prod approval runs here). This
   job does **not** call AWS. It runs
   [`scripts/generate-app-tfvars.sh`](../../scripts/generate-app-tfvars.sh) to
   build `app.auto.tfvars.json` (variables → `app_environment`, secrets →
   `app_secrets`) and uploads it as a workflow artifact.
2. **`deploy` job** — checks out the repo, downloads the Terraform config
   artifact, and assumes `PropelTerraform` via OIDC. The deploy job binds the
   `prod` Environment so the OIDC subject is `environment:prod` (matches
   `prod-trust.json`); approval runs on the `config` job.
3. **Forward Actions variables to env** — vars from the `config` job become shell
   env vars (consumed by the SPA build, e.g. `VITE_*`, `POSTHOG_*`).
4. **Install Terraform app config** — the artifact from `config` is copied to
   `app.auto.tfvars.json` in the prod Terraform directory.
5. **`terraform init` + `apply`**
6. **Build, push & deploy API** — `scripts/deploy-api.sh prod` builds
   `backend.prod.Dockerfile`, pushes to ECR, forces an ECS redeploy.
7. **Build & publish frontend** — `scripts/deploy-frontend.sh prod` runs
   `vite build`, syncs to S3, invalidates CloudFront.

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

Cut a versioned release:

```bash
git tag v1.2.3
git push origin v1.2.3      # triggers deploy-prod.yml; approve in the Environment
```

Or trigger **Deploy Prod** manually from the Actions tab (`workflow_dispatch`).

## Required GitHub config

- **`prod` Environment** (Settings → Environments). The `config` job binds the
  environment so environment-scoped Actions **variables** (e.g. `APP_ENV`,
  `POSTHOG_TOKEN`, `POSTHOG_HOST`) and **secrets** (OAuth client secrets when
  enabled) reach the API via Terraform.
- **`prod` Environment** — add required reviewers to gate prod deploys (runs on
  the `config` job).
- Prod OIDC provider + `PropelTerraform` role (bootstrap Step 4). If prod OIDC
  fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`, re-apply
  `prod-trust.json` (see bootstrap troubleshooting).
