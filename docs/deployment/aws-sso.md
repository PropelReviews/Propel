# AWS SSO (local access)

Local Terraform runs and the `deploy-*.sh` scripts use **ambient AWS
credentials**. In the dev container these come from AWS IAM Identity Center
(SSO), pre-configured so you only need to log in.

## Profiles

The dev container installs `~/.aws/config` from
[`.devcontainer/aws-config`](../../.devcontainer/aws-config) via
`scripts/setup.sh` (`postCreateCommand`). It defines one SSO session and two
profiles:

| Name | Account | Role |
|------|---------|------|
| sso-session `propel` | start URL `https://propel.awsapps.com/start` | — |
| profile `propel-beta` | `536270449640` | `AdministratorAccess` |
| profile `propel-prod` | `616938645090` | `AdministratorAccess` |

No credentials are stored — only the start URL, account IDs, region, and
permission-set names. Short-lived creds are fetched on `aws sso login`.

## Usage

```bash
aws sso login --sso-session propel          # opens a browser verification flow
AWS_PROFILE=propel-beta aws sts get-caller-identity
AWS_PROFILE=propel-prod terraform -chdir=infrastructure/terraform/environments/prod plan
```

Because the providers use ambient credentials (no `assume_role` on the primary
provider), local runs behave identically to CI's OIDC flow.

## Troubleshooting

**`aws: [ERROR] ... The specified sso-session does not exist: "propel"`**

`~/.aws/config` doesn't contain the `propel` session yet. This happens when the
container was built before the SSO config was added, or you hand-wrote a
different config. Install the committed config (backing up any existing one):

```bash
cp ~/.aws/config ~/.aws/config.bak.$(date +%s) 2>/dev/null || true
cp .devcontainer/aws-config ~/.aws/config
aws configure list-profiles        # expect: propel-beta, propel-prod
```

On the next container rebuild, `scripts/setup.sh` installs this automatically
(and won't overwrite an existing `~/.aws/config`).
