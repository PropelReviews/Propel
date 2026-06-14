# Propel documentation

Central index for Propel's documentation. Component-level details live in each
component's own README (linked below); cross-cutting deployment and operations
docs live here under `docs/`.

## Self-hosting

| Doc | What it covers |
|-----|----------------|
| [self-hosting.md](self-hosting.md) | **Self-host guide** — Docker Compose setup, every env var, GitHub App + Linear OAuth integration setup, production checklist. |

## Deployment & operations

| Doc | What it covers |
|-----|----------------|
| [deployment/bootstrap.md](deployment/bootstrap.md) | **One-time AWS setup runbook** — state buckets, OIDC, IAM roles, hosted zones, first apply. Start here for a fresh AWS account. |
| [deployment/cicd.md](deployment/cicd.md) | GitHub Actions workflows: PR checks and beta/prod deploys. |
| [deployment/aws-sso.md](deployment/aws-sso.md) | Local AWS access via SSO profiles in the dev container. |

## Infrastructure reference

| Doc | What it covers |
|-----|----------------|
| [infrastructure/terraform/README.md](../infrastructure/terraform/README.md) | Terraform module/architecture reference (VPC, Aurora, ECS/ALB, S3+CloudFront, DNS) and trade-offs. |
| [infrastructure/docker/README.md](../infrastructure/docker/README.md) | Container images: dev (Compose) vs prod (ECR/ECS), build & push. |
| [infrastructure/README.md](../infrastructure/README.md) | Local stack & dev container overview. |

## Components

- [Backend](../backend/README.md) — FastAPI service (auth, tenants, API).
- [Backend data model](backend/data-model.md) — users, tenants, memberships, invites.
- [Frontend](../frontend/README.md) — Vite + React SPA.
- [Frontend analytics](frontend/analytics.md) — PostHog event taxonomy & super properties.
- [Transformation](../transformation/README.md) — data transformation.
- [Contributing](../CONTRIBUTING.md) — contribution guidelines.

## Quick links

- Self-host with Docker Compose → [self-hosting guide](self-hosting.md)
- New AWS account → [bootstrap runbook](deployment/bootstrap.md)
- Can't `aws sso login` → [AWS SSO troubleshooting](deployment/aws-sso.md#troubleshooting)
- How a deploy happens → [CI/CD](deployment/cicd.md)
