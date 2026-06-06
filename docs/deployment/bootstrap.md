# Bootstrap runbook (one-time AWS setup)

This is the **authoritative, ordered checklist** for standing up Propel's AWS
deployment from nothing. Everything here is done **once per account**; after it
is complete, day-to-day deploys are fully automated by CI/CD (push to `main` for
beta, push a `v*` tag for prod — see [`cicd.md`](cicd.md)).

These steps cannot cleanly create themselves with Terraform (chicken-and-egg:
the state bucket must exist before Terraform can store state; the CI role must
exist before CI can run), so they are manual and done with an
**AdministratorAccess** principal.

## At a glance

| Env  | Account        | State bucket                          | Hosted zone         |
|------|----------------|---------------------------------------|---------------------|
| beta | `536270449640` | `propel-tfstate-beta-536270449640`    | `beta.propel.ninja` |
| prod | `616938645090` | `propel-tfstate-prod-616938645090`    | `propel.ninja`      |

Both accounts share: region `us-east-1`, lock table `propel-tf-locks`, CI role
name `PropelTerraform`, GitHub OIDC provider `token.actions.githubusercontent.com`.

Do **beta first, then prod** — prod's apply reads beta's name servers to wire
the `beta.propel.ninja` delegation, so the beta zone must already exist.

---

## Step 0 — Prerequisites

- Admin access to both AWS accounts (via SSO — see [`aws-sso.md`](aws-sso.md)).
- Permission to create the GitHub OIDC provider, IAM roles, S3, and DynamoDB in
  each account.
- Admin on the `PropelReviews/Propel` GitHub repo (to set Actions variables and
  the `production` Environment).
- Tools: `aws` CLI v2, `terraform` ≥ 1.9.8, `docker`, `jq`. All are preinstalled
  in the dev container.

---

## Step 1 — Authenticate (local)

The dev container ships SSO profiles in `~/.aws/config`. Log in once, then each
command targets an account via `AWS_PROFILE`:

```bash
aws sso login --sso-session propel
AWS_PROFILE=propel-beta aws sts get-caller-identity   # expect 536270449640
AWS_PROFILE=propel-prod aws sts get-caller-identity   # expect 616938645090
```

See [`aws-sso.md`](aws-sso.md) if `aws sso login` errors with
`sso-session does not exist`.

---

## Step 2 — Hosted zones (manual, must exist first)

Terraform **only reads** these zones; it never creates or destroys them.

- **prod account:** `propel.ninja` public hosted zone. The domain registrar's NS
  records must already point at this zone.
- **beta account:** `beta.propel.ninja` public hosted zone — **create it
  manually** in the beta account if it does not exist:

```bash
AWS_PROFILE=propel-beta aws route53 create-hosted-zone \
  --name beta.propel.ninja \
  --caller-reference "propel-bootstrap-$(date +%s)"
```

> You do **not** need to copy the beta NS records into the prod zone by hand —
> prod's Terraform apply does that delegation automatically (cross-account read).

---

## Step 3 — Remote state bucket + lock table (per account)

Terraform stores state in S3 with a DynamoDB lock table, one per account. The
names are fixed in `environments/<env>/backend.tf` (backends can't use
variables), so they must match exactly.

**Beta account:**

```bash
export AWS_PROFILE=propel-beta
aws s3api create-bucket --bucket propel-tfstate-beta-536270449640 --region us-east-1
aws s3api put-bucket-versioning --bucket propel-tfstate-beta-536270449640 \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket propel-tfstate-beta-536270449640 \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket propel-tfstate-beta-536270449640 \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws dynamodb create-table --table-name propel-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
```

**Prod account:** identical, with the prod profile and bucket name:

```bash
export AWS_PROFILE=propel-prod
aws s3api create-bucket --bucket propel-tfstate-prod-616938645090 --region us-east-1
aws s3api put-bucket-versioning --bucket propel-tfstate-prod-616938645090 \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket propel-tfstate-prod-616938645090 \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket propel-tfstate-prod-616938645090 \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws dynamodb create-table --table-name propel-tf-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1

unset AWS_PROFILE
```

> `us-east-1` is special: do **not** pass `--create-bucket-configuration
> LocationConstraint=...`, or the call fails.

---

## Step 4 — GitHub OIDC provider + `PropelTerraform` role (per account)

CI authenticates to AWS with **GitHub OIDC** — short-lived tokens, no stored AWS
keys. Each account needs the OIDC identity provider plus a `PropelTerraform`
role that GitHub Actions assumes.

### 4a. OIDC identity provider (once per account)

> Every `aws` command needs a profile. `aws sso login` only authenticates the
> session — without `AWS_PROFILE` set (or `--profile`), the CLI errors with
> `NoCredentials: Unable to locate credentials`. Set it per account:

```bash
# Prod account, then repeat with AWS_PROFILE=propel-beta for the beta account
export AWS_PROFILE=propel-prod
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 4b. `PropelTerraform` role + trust policy

The trust/permission policy JSON is committed under
[`infrastructure/terraform/bootstrap/`](../../infrastructure/terraform/bootstrap/README.md)
(safe to commit — account IDs and policy JSON only, no secrets):

- `beta-trust.json` — beta trust: GitHub `main` branch, the `beta` environment,
  **and** prod cross-account assume (the `ProdCrossAccountAssume` statement, so
  the role is created in one shot).
- `prod-trust.json` — prod trust: GitHub `v*` tags + `production` environment.

Create the roles — **prod first**, because `beta-trust.json` names the prod role
as a principal and IAM validates that it exists (run from the repo root):

```bash
AWS_PROFILE=propel-prod aws iam create-role --role-name PropelTerraform \
  --assume-role-policy-document file://infrastructure/terraform/bootstrap/prod-trust.json
AWS_PROFILE=propel-beta aws iam create-role --role-name PropelTerraform \
  --assume-role-policy-document file://infrastructure/terraform/bootstrap/beta-trust.json
```

> **Roles already exist?** Use `update-assume-role-policy` (same `--policy-document`
> paths) instead of `create-role`.
>
> If you hit `MalformedPolicyDocument: Invalid principal`, the prod role didn't
> exist yet — create it first, then re-apply the beta trust.

### 4c. Cross-account trust — prod side (permissions)

The **beta side** is handled by the `ProdCrossAccountAssume` statement in
`beta-trust.json` (4b). The **prod side** is a *permissions* policy (not a trust
policy). `PowerUserAccess` (4d) already grants `sts:AssumeRole`, but attaching it
explicitly is clearer:

```bash
AWS_PROFILE=propel-prod aws iam put-role-policy \
  --role-name PropelTerraform \
  --policy-name AssumeBetaDnsRole \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sts:AssumeRole","Resource":"arn:aws:iam::536270449640:role/PropelTerraform"}]}'
```

> `beta-trust.json` also allows the prod **account root** to assume the beta
> role, so a *local* prod `terraform apply` (run as your SSO admin, not the prod
> deploy role) can do the cross-account DNS read. CI uses the prod deploy role,
> which is trusted directly. Drop that principal if you only deploy prod via CI.

The prod environment passes the beta role ARN to Terraform via
`beta_dns_role_arn` (`providers.tf`, alias `aws.beta_dns`).

### 4d. Permissions

`PowerUserAccess` **excludes all IAM write actions**, but the stack creates the
ECS task + execution roles — so the deploy role also needs a scoped IAM policy
(`iam-deploy-policy.json`, limited to `propel-*` roles + the required
service-linked roles). Attach both to **each** account's role:

```bash
for p in propel-beta propel-prod; do
  AWS_PROFILE=$p aws iam attach-role-policy --role-name PropelTerraform \
    --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
  AWS_PROFILE=$p aws iam put-role-policy --role-name PropelTerraform \
    --policy-name PropelDeployIam \
    --policy-document file://infrastructure/terraform/bootstrap/iam-deploy-policy.json
done
```

> Skipping the IAM policy is a common first-deploy failure: a CI apply dies with
> an access-denied the moment it tries to create the ECS task/execution roles. A
> *local* apply as `AdministratorAccess` masks this, because your SSO admin can
> manage IAM regardless.

---

## Step 5 — GitHub repo configuration

App config is **not hardcoded** — every GitHub Actions **variable** (org or repo
level) is forwarded by the workflows into both the API container env
(`app_environment` → `app.auto.tfvars.json`) and the SPA build env. Adding a new
key is just adding an Actions variable; no Terraform or workflow edits needed.

1. **Environments + Actions variables** — create **`beta`** and **`production`**
   environments (Settings → Environments). Add Actions **variables** on each
   (or at org/repo level as a fallback). The PostHog project token is a
   write-only key, safe as a variable:

   | Variable | Example | Consumed by |
   |----------|---------|-------------|
   | `POSTHOG_TOKEN` | `phc_...` | API (OTEL → PostHog) + SPA |
   | `POSTHOG_HOST` | `https://us.i.posthog.com` | API + SPA |

   Deploy workflows bind `environment: beta` / `environment: production` so
   environment-scoped variables are forwarded via `vars` into the API container
   and SPA build. Without the environment binding, only repo/org variables are
   visible and per-environment values (e.g. beta PostHog) are silently omitted.

   For **truly sensitive** values, use the Terraform `app_secrets` map instead —
   each entry becomes a Secrets Manager secret injected into the task.

2. **`production` Environment** — add **required reviewers** so prod deploys
   pause for manual approval. Prod also auto-triggers after a successful beta
   deploy on `main` (see [`cicd.md`](cicd.md)).

---

## Step 6 — First Terraform apply

Run locally with each account's credentials. **Beta before prod.**

```bash
# Beta
export AWS_PROFILE=propel-beta
cd infrastructure/terraform/environments/beta
terraform init
terraform apply

# Prod (also writes the beta.propel.ninja NS delegation into propel.ninja)
export AWS_PROFILE=propel-prod
cd ../prod
terraform init
terraform apply
unset AWS_PROFILE
```

This provisions VPC, Aurora Serverless v2, ECS/ALB, S3+CloudFront, ACM certs,
and Route53 records. ACM DNS validation can take a few minutes.

> CI runs this same `init`/`apply` automatically; the first local apply just
> proves the bootstrap is correct and seeds state.

---

## Step 7 — First image + frontend publish

ECS starts with **0 healthy tasks** until the first image exists. Seed both:

```bash
AWS_PROFILE=propel-beta ./scripts/deploy-api.sh beta
AWS_PROFILE=propel-beta ./scripts/deploy-frontend.sh beta
```

(After this, CI does it on every push to `main` / `v*` tag.)

---

## Step 8 — Verify

```bash
curl https://api.beta.propel.ninja/health   # {"status":"ok"}
open https://app.beta.propel.ninja
```

For prod, swap to `api.propel.ninja` / `app.propel.ninja`.

---

## Done — what runs automatically now

| Trigger | Workflow | Result |
|---------|----------|--------|
| PR / push to `main` | `ci.yml` | `terraform fmt`+`validate`, backend `pytest`, frontend `vitest` |
| push to `main` | `deploy-beta.yml` | apply beta + deploy API + frontend |
| push `v*` tag | `deploy-prod.yml` | (after approval) apply prod + deploy API + frontend |

---

## Teardown / rebuild notes

- Buckets, lock tables, OIDC providers, and IAM roles are **not** managed by
  Terraform — destroying the stack leaves them in place. Remove them by hand if
  decommissioning an account.
- The state bucket has versioning on; empty all versions before deleting it.
- Hosted zones are never touched by Terraform.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `NoCredentials: Unable to locate credentials` | `AWS_PROFILE` not set — `aws sso login` authenticates the session but commands still need a profile. Run `export AWS_PROFILE=propel-prod` (or `propel-beta`), or pass `--profile`. |
| `sso-session does not exist: "propel"` | `~/.aws/config` missing the profiles — see [`aws-sso.md`](aws-sso.md). |
| OIDC `EntityAlreadyExists` | The provider already exists in that account (only one allowed) — safe to skip 4a; verify with `aws iam list-open-id-connect-providers`. |
| `Backend initialization required` on `plan`/`apply` | Run `terraform init` first; ensure the state bucket + lock table from Step 3 exist. |
| `BucketAlreadyOwnedByYou` | The state bucket is already created — safe to ignore. |
| Prod apply can't read beta zone | Step 4c cross-account trust is missing or `beta_dns_role_arn` is wrong. |
| ALB target unhealthy / 0 tasks | No image pushed yet — run Step 7. |
| ACM cert stuck `PENDING_VALIDATION` | DNS validation records propagating; wait a few minutes and re-apply. |
