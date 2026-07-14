terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = var.subnet_ids
  tags       = var.tags

  lifecycle {
    # PostHog CDC uses public subnets so Aurora can take a public IP; in-place
    # updates are supported without replacing the subnet group.
    create_before_destroy = true
  }
}

# Master password generated and kept in Terraform state + Secrets Manager.
# special chars restricted to ones that are safe inside a postgres:// URL.
resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "-_"
}

resource "aws_rds_cluster" "this" {
  cluster_identifier = "${var.name_prefix}-aurora"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = var.engine_version

  allow_major_version_upgrade = true

  database_name   = var.db_name
  master_username = var.master_username
  master_password = random_password.master.result

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.rds_security_group_id]

  db_cluster_parameter_group_name = (
    var.posthog_warehouse_enabled
    ? aws_rds_cluster_parameter_group.posthog[0].name
    : null
  )

  # Data API (query editor / ExecuteStatement) for debugging without VPC access.
  enable_http_endpoint = var.enable_data_api

  storage_encrypted         = true
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name_prefix}-aurora-final"
  deletion_protection       = var.deletion_protection

  serverlessv2_scaling_configuration {
    min_capacity             = var.min_acu
    max_capacity             = var.max_acu
    # Only valid when min_capacity is 0; omit otherwise (AWS rejects it).
    seconds_until_auto_pause = var.min_acu == 0 ? var.seconds_until_auto_pause : null
  }

  tags = var.tags
}

resource "aws_rds_cluster_instance" "writer" {
  identifier         = "${var.name_prefix}-aurora-1"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version

  # PostHog connects over the internet (sslmode=require) from fixed egress IPs.
  publicly_accessible = var.posthog_warehouse_enabled
  apply_immediately   = var.posthog_warehouse_enabled

  lifecycle {
    # Subnet group changes (private → public for PostHog) require a new ENI in an
    # IGW-routed subnet; replacing the writer is the supported migration path.
    replace_triggered_by = [
      aws_db_subnet_group.this.id,
    ]
  }

  tags = var.tags
}

locals {
  database_url = format(
    "postgresql://%s:%s@%s:5432/%s",
    var.master_username,
    random_password.master.result,
    aws_rds_cluster.this.endpoint,
    var.db_name,
  )
}

# Full connection string stored as a Secrets Manager secret. The ECS task
# injects this value into the DATABASE_URL env var via the `secrets` block.
resource "aws_secretsmanager_secret" "database_url" {
  name        = "${var.name_prefix}/database-url"
  description = "Postgres connection string for the ${var.name_prefix} API."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = local.database_url
}
