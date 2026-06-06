# Bootstrap IAM policies

Canonical IAM trust and permission policies for the per-account
`PropelTerraform` deploy roles that GitHub Actions assumes via OIDC. These are
applied **once per account** during the [bootstrap runbook](../../../docs/deployment/bootstrap.md)
(Step 4) — they are *not* managed by Terraform (the role is what runs Terraform,
so it can't manage itself).

These files are safe to commit: they contain only AWS account IDs, the GitHub
repo path, and policy JSON — **no credentials or secrets**.

| File | Role | Kind | Purpose |
|------|------|------|---------|
| `beta-trust.json` | beta `PropelTerraform` | trust policy | Lets GitHub Actions (`main` branch) assume the role, **and** lets the prod account assume it for the cross-account DNS read. |
| `prod-trust.json` | prod `PropelTerraform` | trust policy | Lets GitHub Actions (`v*` tags, `main` branch, + `prod` environment) assume the role. |
| `iam-deploy-policy.json` | both | permissions policy | Allows managing the `propel-*` ECS task/exec roles + required service-linked roles (`PowerUserAccess` excludes IAM). |

## Apply

Run from the repo root, once per account (see the runbook for full context):

```bash
# Roles (create prod first — beta-trust.json references the prod role as a principal)
AWS_PROFILE=propel-prod aws iam create-role --role-name PropelTerraform \
  --assume-role-policy-document file://infrastructure/terraform/bootstrap/prod-trust.json
AWS_PROFILE=propel-beta aws iam create-role --role-name PropelTerraform \
  --assume-role-policy-document file://infrastructure/terraform/bootstrap/beta-trust.json

# If the roles already exist, update the trust policies instead:
AWS_PROFILE=propel-prod aws iam update-assume-role-policy --role-name PropelTerraform \
  --policy-document file://infrastructure/terraform/bootstrap/prod-trust.json
AWS_PROFILE=propel-beta aws iam update-assume-role-policy --role-name PropelTerraform \
  --policy-document file://infrastructure/terraform/bootstrap/beta-trust.json

# Permissions (both accounts) + PowerUserAccess + the prod cross-account assume grant
for p in propel-beta propel-prod; do
  AWS_PROFILE=$p aws iam put-role-policy --role-name PropelTerraform \
    --policy-name PropelDeployIam \
    --policy-document file://infrastructure/terraform/bootstrap/iam-deploy-policy.json
  AWS_PROFILE=$p aws iam attach-role-policy --role-name PropelTerraform \
    --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
done

AWS_PROFILE=propel-prod aws iam put-role-policy --role-name PropelTerraform \
  --policy-name AssumeBetaDnsRole \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"sts:AssumeRole","Resource":"arn:aws:iam::536270449640:role/PropelTerraform"}]}'
```

> `beta-trust.json` allows the prod **account root** to assume the beta role so a
> local prod `terraform apply` (run as your SSO admin) can do the cross-account
> DNS read. If you only ever deploy prod via CI, you can drop that principal and
> keep just `arn:aws:iam::616938645090:role/PropelTerraform`.
