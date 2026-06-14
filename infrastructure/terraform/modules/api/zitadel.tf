# ------------------------------------------------------------------------------
# Zitadel: self-hosted identity provider (OIDC) served at auth.<zone> through the
# shared ALB. Two ECS Fargate services share the cluster + image-pull/secret IAM
# roles with the API:
#   * zitadel        — the API/console (`start-from-init`), port 8080
#   * zitadel-login  — the hosted Login UI v2, port 3000
# They share a small EFS volume (/zitadel/bootstrap) that Zitadel seeds with the
# admin + login-client PATs on first boot (mirrors the compose `zitadel-bootstrap`
# volume). Zitadel owns its own `zitadel` database on the shared Aurora cluster:
# `start-from-init` with the Aurora master (admin) creds creates the database +
# unprivileged user automatically, so there is no manual DB step.
#
# Everything is `count = var.zitadel_enabled ? 1 : 0` so environments opt in and
# this can merge before the first cloud apply without touching existing infra.
#
# The resources are split across sibling files (all in this module):
#   * zitadel_secrets.tf — Secrets Manager secrets/placeholders + IAM read policies
#   * zitadel_compute.tf — EFS volume, ECS task defs/services, ECS Exec policy
#   * zitadel_network.tf — Cloud Map, ALB target groups/rules, ECS SG rules
# This file holds the shared locals consumed by all three.
# ------------------------------------------------------------------------------

locals {
  zitadel_enabled = var.zitadel_enabled
  # The API "consumes" Zitadel (needs an OIDC app + client secrets) whenever an
  # issuer URL is set, even in environments that don't host the instance. Beta
  # points at the single prod instance; prod points at itself.
  zitadel_consumer       = var.zitadel_issuer_url != ""
  zitadel_namespace_name = "${var.name_prefix}-auth.local"
  # Internal DNS the Login UI uses to reach the Zitadel API (Cloud Map).
  zitadel_internal_api_url = "http://zitadel.${local.zitadel_namespace_name}:8080"
  zitadel_bootstrap_path   = "/zitadel/bootstrap"
  zitadel_pat_expiration   = "2099-01-01T00:00:00Z"

  # Non-secret Zitadel API env. Passwords + masterkey come from Secrets Manager
  # (local.zitadel_secrets). Structured Postgres config (not a DSN) so we can
  # supply Admin creds for first-boot DB/user creation.
  zitadel_environment = {
    ZITADEL_PORT           = "8080"
    ZITADEL_EXTERNALDOMAIN = var.auth_fqdn
    ZITADEL_EXTERNALPORT   = "443"
    ZITADEL_EXTERNALSECURE = "true"
    ZITADEL_TLS_ENABLED    = "false"

    ZITADEL_DATABASE_POSTGRES_HOST          = var.db_cluster_endpoint
    ZITADEL_DATABASE_POSTGRES_PORT          = "5432"
    ZITADEL_DATABASE_POSTGRES_DATABASE      = "zitadel"
    ZITADEL_DATABASE_POSTGRES_USER_USERNAME = var.db_master_username
    ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE = "require"
    # Admin connection (Aurora master) only used on init to CREATE DATABASE/ROLE.
    ZITADEL_DATABASE_POSTGRES_ADMIN_USERNAME = var.db_master_username
    ZITADEL_DATABASE_POSTGRES_ADMIN_SSL_MODE = "require"

    # Seed the IAM_OWNER admin PAT + login-client PAT onto the shared EFS volume,
    # exactly like the local compose bootstrap. deploy-zitadel.sh copies the
    # admin PAT into Secrets Manager for the bootstrap step.
    ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORDCHANGEREQUIRED   = "false"
    ZITADEL_FIRSTINSTANCE_PATPATH                            = "${local.zitadel_bootstrap_path}/admin.pat"
    ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_USERNAME       = "propel-admin"
    ZITADEL_FIRSTINSTANCE_ORG_MACHINE_MACHINE_NAME           = "Propel Bootstrap"
    ZITADEL_FIRSTINSTANCE_ORG_MACHINE_PAT_EXPIRATIONDATE     = local.zitadel_pat_expiration
    ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH                 = "${local.zitadel_bootstrap_path}/login-client.pat"
    ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_USERNAME   = "login-client"
    ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_MACHINE_NAME       = "Propel Login Client"
    ZITADEL_FIRSTINSTANCE_ORG_LOGINCLIENT_PAT_EXPIRATIONDATE = local.zitadel_pat_expiration

    # Force Login UI v2 and point its hosted URLs at auth.<zone>.
    ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_REQUIRED = "true"
    ZITADEL_DEFAULTINSTANCE_FEATURES_LOGINV2_BASEURI  = "https://${var.auth_fqdn}/ui/v2/login/"
    ZITADEL_OIDC_DEFAULTLOGINURLV2                    = "https://${var.auth_fqdn}/ui/v2/login/login?authRequest="
    ZITADEL_OIDC_DEFAULTLOGOUTURLV2                   = "https://${var.auth_fqdn}/ui/v2/login/logout?post_logout_redirect="
    ZITADEL_SAML_DEFAULTLOGINURLV2                    = "https://${var.auth_fqdn}/ui/v2/login/login?samlRequest="
    ZITADEL_LOGSTORE_ACCESS_STDOUT_ENABLED            = "true"
  }

  zitadel_secrets = local.zitadel_enabled ? [
    { name = "ZITADEL_MASTERKEY", valueFrom = aws_secretsmanager_secret.zitadel_masterkey[0].arn },
    { name = "ZITADEL_DATABASE_POSTGRES_USER_PASSWORD", valueFrom = aws_secretsmanager_secret.zitadel_db_password[0].arn },
    { name = "ZITADEL_DATABASE_POSTGRES_ADMIN_PASSWORD", valueFrom = aws_secretsmanager_secret.zitadel_db_password[0].arn },
  ] : []
}
