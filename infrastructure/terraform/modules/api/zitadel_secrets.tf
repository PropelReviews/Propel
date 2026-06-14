# ------------------------------------------------------------------------------
# Zitadel secrets (see zitadel.tf for the module overview).
#
# Instance secrets (master key + Aurora DB password) exist only where the Zitadel
# containers run (zitadel_enabled). OIDC client id/secret, the management PAT, and
# the Actions signing key exist in every *consuming* environment (zitadel_consumer)
# and are seeded as placeholders here, then overwritten by the deploy-time
# bootstrap step (ignore_changes keeps Terraform from clobbering them).
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Secrets: master encryption key (generated once) + the Aurora master password
# Zitadel uses for its DB user/admin connection.
# ------------------------------------------------------------------------------
resource "random_password" "zitadel_masterkey" {
  count   = local.zitadel_enabled ? 1 : 0
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "zitadel_masterkey" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}/zitadel/MASTERKEY"
  description = "Zitadel master encryption key for ${var.name_prefix}."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_masterkey" {
  count         = local.zitadel_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_masterkey[0].id
  secret_string = random_password.zitadel_masterkey[0].result

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "zitadel_db_password" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}/zitadel/DB_PASSWORD"
  description = "Aurora password Zitadel uses for its DB user + admin connection."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_db_password" {
  count         = local.zitadel_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_db_password[0].id
  secret_string = var.db_master_password
}

# OIDC client id + secret consumed by the API. These exist in *every* consuming
# environment (beta + prod), since each environment registers its own OIDC app
# against the single Zitadel instance and stores the resulting credentials in its
# own account's Secrets Manager. Terraform creates placeholders (ignore_changes)
# on first apply; the deploy-time bootstrap step (scripts/zitadel_bootstrap.py
# --env <env>) creates the real OIDC app in the shared Zitadel and overwrites
# these values, then deploy-api.sh rolls the API to pick them up.
resource "aws_secretsmanager_secret" "zitadel_client_id" {
  count       = local.zitadel_consumer ? 1 : 0
  name        = "${var.name_prefix}/app/ZITADEL_CLIENT_ID"
  description = "Zitadel OIDC client id (provisioned by the bootstrap step)."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_client_id" {
  count         = local.zitadel_consumer ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_client_id[0].id
  secret_string = "pending-bootstrap"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "zitadel_client_secret" {
  count       = local.zitadel_consumer ? 1 : 0
  name        = "${var.name_prefix}/app/ZITADEL_CLIENT_SECRET"
  description = "Zitadel OIDC client secret (provisioned by the bootstrap step)."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_client_secret" {
  count         = local.zitadel_consumer ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_client_secret[0].id
  secret_string = "pending-bootstrap"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Beta consumes the prod Zitadel but holds its own copy of the prod *management*
# PAT so its deploy pipeline can register/refresh the "Propel Beta" OIDC app
# against the shared instance. The beta deploy job cannot read environment-scoped
# GitHub secrets (its OIDC subject must stay refs/heads/main), so CI forwards the
# PAT through the config job into var.zitadel_mgmt_token and Terraform seeds it
# here, where deploy-zitadel.sh then reads it from Secrets Manager.
resource "aws_secretsmanager_secret" "zitadel_mgmt_token" {
  count       = local.zitadel_consumer ? 1 : 0
  name        = "${var.name_prefix}/zitadel/MGMT_TOKEN"
  description = "Zitadel IAM_OWNER PAT used by this env's bootstrap step."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_mgmt_token" {
  count     = local.zitadel_consumer ? 1 : 0
  secret_id = aws_secretsmanager_secret.zitadel_mgmt_token[0].id
  # When CI supplies the PAT (beta always; prod once the admin sets it) Terraform
  # owns the value. Empty keeps the placeholder so prod's first boot — where the
  # PAT only exists on the EFS bootstrap volume — is not overwritten; prod's
  # deploy-zitadel.sh reads that first PAT from EFS directly.
  secret_string = var.zitadel_mgmt_token != "" ? var.zitadel_mgmt_token : "pending-sync"
}

# HMAC signing key for Zitadel Actions V2 webhooks (GitHub IdP mapping). Written
# by deploy-zitadel.sh when the bootstrap registers the Actions V2 target.
resource "aws_secretsmanager_secret" "zitadel_actions_signing_key" {
  count       = local.zitadel_consumer ? 1 : 0
  name        = "${var.name_prefix}/zitadel/ACTIONS_SIGNING_KEY"
  description = "Zitadel Actions V2 signing key for GitHub IdP mapping webhook."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_actions_signing_key" {
  count         = local.zitadel_consumer ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_actions_signing_key[0].id
  secret_string = "pending-bootstrap"

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# The shared ECS execution role must be allowed to read the OIDC client secrets
# so the API task can hydrate them. Present in every consuming environment.
data "aws_iam_policy_document" "zitadel_client_secrets" {
  count = local.zitadel_consumer ? 1 : 0
  statement {
    sid     = "ReadZitadelClientSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.zitadel_client_id[0].arn,
      aws_secretsmanager_secret.zitadel_client_secret[0].arn,
      aws_secretsmanager_secret.zitadel_actions_signing_key[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "zitadel_client_secrets" {
  count  = local.zitadel_consumer ? 1 : 0
  name   = "${var.name_prefix}-zitadel-client-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.zitadel_client_secrets[0].json
}

# Instance-only secrets (master key + Aurora DB password) — read only where the
# Zitadel containers actually run (prod).
data "aws_iam_policy_document" "zitadel_instance_secrets" {
  count = local.zitadel_enabled ? 1 : 0
  statement {
    sid     = "ReadZitadelInstanceSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [
      aws_secretsmanager_secret.zitadel_masterkey[0].arn,
      aws_secretsmanager_secret.zitadel_db_password[0].arn,
    ]
  }
}

resource "aws_iam_role_policy" "zitadel_instance_secrets" {
  count  = local.zitadel_enabled ? 1 : 0
  name   = "${var.name_prefix}-zitadel-instance-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.zitadel_instance_secrets[0].json
}
