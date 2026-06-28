# PostHog data-warehouse Postgres CDC: logical replication, public endpoint, and
# a dedicated login stored in Secrets Manager. The role + publication are created
# by Alembic migration 007 when POSTHOG_WAREHOUSE_DB_PASSWORD is injected at API
# boot (same password as this secret).

locals {
  # Family must match the cluster major version (e.g. 18.3 → aurora-postgresql18).
  # Uses var.engine_version (not aws_rds_cluster.this) — the cluster references this
  # parameter group, so reading the cluster here would create a Terraform cycle.
  posthog_parameter_group_family = "aurora-postgresql${split(".", var.engine_version)[0]}"
}

resource "aws_rds_cluster_parameter_group" "posthog" {
  count = var.posthog_warehouse_enabled ? 1 : 0
  # Stable name — do not embed engine_version; AWS won't delete a group while the
  # cluster still references it, and a version suffix forces a doomed replace.
  name   = "${var.name_prefix}-aurora-posthog"
  family = local.posthog_parameter_group_family

  parameter {
    name         = "rds.logical_replication"
    value        = "1"
    apply_method = "pending-reboot"
  }

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "random_password" "posthog_warehouse" {
  count            = var.posthog_warehouse_enabled ? 1 : 0
  length           = 32
  special          = true
  override_special = "-_"
}

resource "aws_secretsmanager_secret" "posthog_warehouse" {
  count       = var.posthog_warehouse_enabled ? 1 : 0
  name        = "${var.name_prefix}/posthog-warehouse"
  description = "PostHog data-warehouse Postgres CDC credentials for ${var.name_prefix}."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "posthog_warehouse" {
  count     = var.posthog_warehouse_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.posthog_warehouse[0].id
  secret_string = jsonencode({
    username    = var.posthog_warehouse_username
    password    = random_password.posthog_warehouse[0].result
    host        = aws_rds_cluster_instance.writer.endpoint
    port        = 5432
    dbname      = var.db_name
    sslmode     = "require"
    publication = var.posthog_warehouse_publication
    connection_url = format(
      "postgresql://%s:%s@%s:5432/%s?sslmode=require",
      var.posthog_warehouse_username,
      urlencode(random_password.posthog_warehouse[0].result),
      aws_rds_cluster_instance.writer.endpoint,
      var.db_name,
    )
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
