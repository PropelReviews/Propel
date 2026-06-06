# Terraform: AWS deployment (beta + prod)

Infrastructure-as-code for Propel's AWS deployment, in **us-east-1**:

- **Aurora PostgreSQL Serverless v2** (private subnets)
- **FastAPI on ECS Fargate** behind a **public HTTPS ALB**
- **Vite app + landing site on S3 + CloudFront** (private buckets, Origin Access Control)
- **ACM + Route53** for TLS and DNS
- **No CloudWatch** — the API ships observability to PostHog via OpenTelemetry

```
modules/
  network/    VPC (2 AZs, public/private), single NAT, ALB/ECS/RDS security groups
  database/   Aurora Serverless v2 cluster + writer, Secrets Manager DATABASE_URL
  api/        ECR, ECS Fargate cluster/task/service (no logConfiguration), ALB
  frontend/   private S3 bucket + CloudFront (OAC, SPA fallback) for the app
  landing/    private S3 bucket + CloudFront for the marketing site (apex + www,
              www->apex redirect via CloudFront Function)
  dns/        ACM cert (DNS-validated) for api + app + landing (apex/www) FQDNs
  stack/      composes all of the above + Route53 alias records
environments/
  beta/       account 536270449640, zone beta.propel.ninja
  prod/       account 616938645090, zone propel.ninja (+ beta NS delegation)
```

## Accounts & domains

| Env  | Account        | Zone                | API                       | App                       | Landing (apex + www)                          |
|------|----------------|---------------------|---------------------------|---------------------------|-----------------------------------------------|
| beta | 536270449640   | `beta.propel.ninja` | `api.beta.propel.ninja`   | `app.beta.propel.ninja`   | `beta.propel.ninja`, `www.beta.propel.ninja`  |
| prod | 616938645090   | `propel.ninja`      | `api.propel.ninja`        | `app.propel.ninja`        | `propel.ninja`, `www.propel.ninja`            |

The landing site is served from the zone apex and `www`; `www.*` is 301-redirected
to the apex (the canonical URL) by a CloudFront Function. The app stays on `app.*`.

The prod config delegates `beta.propel.ninja` from the `propel.ninja` zone by
reading the beta zone's name servers cross-account (read-only) and writing the
NS record in the parent zone. Both hosted zones are **referenced** (never
created/destroyed by Terraform).

`www.beta.propel.ninja` is **not** a separate hosted zone and does **not** need
its own NS record in the prod zone. Delegation at `beta.propel.ninja` already
covers all child names; the beta stack creates a Route53 **A alias** for `www`
in the `beta.propel.ninja` child zone pointing at the beta landing CloudFront
distribution. Do not add a `www.beta.propel.ninja` NS record in prod — that
breaks resolution and leaves clients seeing only NS/SOA responses.

---

## One-time prerequisites (manual, per account)

> **The full step-by-step is the [bootstrap runbook](../../docs/deployment/bootstrap.md).**
> This section is a summary; follow the runbook for the exact commands and order.

Done once per account before the first `terraform init`:

1. **Hosted zones** — `propel.ninja` (prod) and `beta.propel.ninja` (beta,
   manually created). Terraform only reads them.
2. **Remote state** — an S3 bucket + `propel-tf-locks` DynamoDB table per
   account (names fixed in `environments/<env>/backend.tf`).
3. **GitHub OIDC + `PropelTerraform` role** per account, with prod→beta
   cross-account trust for the DNS delegation. Local runs instead use AWS SSO
   ([aws-sso.md](../../docs/deployment/aws-sso.md)).

### App config via GitHub Actions variables (generic)

App configuration is **not hardcoded** anywhere. Every **GitHub Actions
variable** (org or repo level) is forwarded generically by the workflows into:

- the **API container** env — via `app_environment` (CI writes
  `{"app_environment": ${{ toJSON(vars) }}}` to `app.auto.tfvars.json`, which
  Terraform auto-loads), and
- the **SPA build** env — the workflow exports all variables to `$GITHUB_ENV`.

So adding a new key (e.g. `POSTHOG_TOKEN`, `POSTHOG_HOST`, `VITE_FEATURE_X`)
is just **adding an Actions variable** — no Terraform or workflow edits.

Typical variables to set at the org level (the PostHog write-only key is safe to
expose as a variable):

| Variable | Example | Consumed by |
|----------|---------|-------------|
| `POSTHOG_TOKEN` | `phc_...` | API (OTEL -> PostHog) + SPA |
| `POSTHOG_HOST` | `https://us.i.posthog.com` | API + SPA |

For **truly sensitive** values (not safe to expose), use the `app_secrets`
variable instead: each entry becomes a Secrets Manager secret injected into the
task. Set it locally in `terraform.tfvars`, or wire specific GitHub **secrets**
into `app.auto.tfvars.json` in the workflow. To diverge config per environment,
use GitHub **Environment-scoped** variables.

Include `JWT_SECRET` and OAuth client secrets (`OAUTH_GOOGLE_CLIENT_SECRET`,
`OAUTH_GITHUB_CLIENT_SECRET`) in `app_secrets`; non-secret OAuth client IDs
can live in `app_environment` (GitHub Actions variables).

---

## Deploy

### First time

See the [bootstrap runbook](../../docs/deployment/bootstrap.md) — it covers
state buckets, OIDC/IAM, hosted zones, the **beta-before-prod** apply order, and
seeding the first API image + frontend.

### Ongoing (CI/CD)

- Push to `main` -> `.github/workflows/deploy-beta.yml` deploys **beta**.
- Push a `v*` tag -> `.github/workflows/deploy-prod.yml` deploys **prod**
  (gated by the `production` GitHub Environment approval).

### Verify

```bash
curl https://api.beta.propel.ninja/health   # {"status":"ok"}
open https://app.beta.propel.ninja           # app (dashboard)
open https://beta.propel.ninja               # landing (www redirects here)
```

---

## Notes & trade-offs

- **No CloudWatch:** ECS task definitions omit `logConfiguration`; there are no
  log groups, dashboards, or alarms. App-level observability goes to PostHog.
- **No autoscaling:** target tracking needs CloudWatch, so `api_desired_count`
  is fixed per environment.
- **Single NAT gateway** per environment (~$32/mo) is the main fixed cost; ECS
  tasks pull from ECR and reach PostHog through it. VPC endpoints could remove
  it later.
- **State** is per account in S3 with DynamoDB locking.
- Terraform does **not** manage the hosted zones or the registrar delegation.
