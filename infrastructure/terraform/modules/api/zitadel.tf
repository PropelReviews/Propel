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
# against the shared instance. Provisioned empty here and populated once (synced
# from prod, or pasted) — ignore_changes keeps Terraform from clobbering it.
resource "aws_secretsmanager_secret" "zitadel_mgmt_token" {
  count       = local.zitadel_consumer && !local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}/zitadel/MGMT_TOKEN"
  description = "Prod Zitadel IAM_OWNER PAT used by this env's bootstrap step."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "zitadel_mgmt_token" {
  count         = local.zitadel_consumer && !local.zitadel_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.zitadel_mgmt_token[0].id
  secret_string = "pending-sync"

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

# ------------------------------------------------------------------------------
# EFS: shared /zitadel/bootstrap volume for the admin + login-client PATs.
# ------------------------------------------------------------------------------
resource "aws_security_group" "zitadel_efs" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}-zitadel-efs"
  description = "NFS from ECS tasks to the Zitadel bootstrap EFS"
  vpc_id      = var.vpc_id

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-zitadel-efs" })
}

resource "aws_efs_file_system" "zitadel" {
  count          = local.zitadel_enabled ? 1 : 0
  creation_token = "${var.name_prefix}-zitadel-bootstrap"
  encrypted      = true
  tags           = merge(var.tags, { Name = "${var.name_prefix}-zitadel-bootstrap" })
}

resource "aws_efs_mount_target" "zitadel" {
  count           = local.zitadel_enabled ? length(var.private_subnet_ids) : 0
  file_system_id  = aws_efs_file_system.zitadel[0].id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.zitadel_efs[0].id]
}

resource "aws_efs_access_point" "zitadel" {
  count          = local.zitadel_enabled ? 1 : 0
  file_system_id = aws_efs_file_system.zitadel[0].id

  posix_user {
    uid = 0
    gid = 0
  }

  root_directory {
    path = local.zitadel_bootstrap_path
    creation_info {
      owner_uid   = 0
      owner_gid   = 0
      permissions = "0755"
    }
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Service discovery: the Login UI resolves the Zitadel API at
# zitadel.<name_prefix>-auth.local (registered by the zitadel ECS service below).
# ------------------------------------------------------------------------------
resource "aws_service_discovery_private_dns_namespace" "zitadel" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = local.zitadel_namespace_name
  description = "Private service discovery for ${var.name_prefix} Zitadel."
  vpc         = var.vpc_id
  tags        = var.tags
}

resource "aws_service_discovery_service" "zitadel" {
  count = local.zitadel_enabled ? 1 : 0
  name  = "zitadel"

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.zitadel[0].id
    routing_policy = "MULTIVALUE"
    dns_records {
      type = "A"
      ttl  = 10
    }
  }

  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Task definitions
# ------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "zitadel" {
  count                    = local.zitadel_enabled ? 1 : 0
  family                   = "${var.name_prefix}-zitadel"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.zitadel_task_cpu
  memory                   = var.zitadel_task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  volume {
    name = "zitadel-bootstrap"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.zitadel[0].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.zitadel[0].id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "zitadel"
    image     = var.zitadel_image
    essential = true
    user      = "0"
    # --masterkeyFromEnv reads ZITADEL_MASTERKEY (a secret); --tlsMode external
    # because the ALB terminates TLS and Zitadel serves plain HTTP behind it.
    command     = ["start-from-init", "--masterkeyFromEnv", "--tlsMode", "external"]
    environment = [for k, v in local.zitadel_environment : { name = k, value = v }]
    secrets     = local.zitadel_secrets

    portMappings = [{ containerPort = 8080, protocol = "tcp" }]

    mountPoints = [{
      sourceVolume  = "zitadel-bootstrap"
      containerPath = local.zitadel_bootstrap_path
      readOnly      = false
    }]

    healthCheck = {
      command     = ["CMD", "/app/zitadel", "ready"]
      interval    = 15
      timeout     = 5
      retries     = 5
      startPeriod = 120
    }
  }])

  tags = var.tags
}

resource "aws_ecs_task_definition" "zitadel_login" {
  count                    = local.zitadel_enabled ? 1 : 0
  family                   = "${var.name_prefix}-zitadel-login"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.zitadel_login_task_cpu
  memory                   = var.zitadel_login_task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  volume {
    name = "zitadel-bootstrap"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.zitadel[0].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.zitadel[0].id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "zitadel-login"
    image     = var.zitadel_login_image
    essential = true
    user      = "0"
    environment = [for k, v in {
      ZITADEL_API_URL                 = local.zitadel_internal_api_url
      NEXT_PUBLIC_BASE_PATH           = "/ui/v2/login"
      ZITADEL_SERVICE_USER_TOKEN_FILE = "${local.zitadel_bootstrap_path}/login-client.pat"
      CUSTOM_REQUEST_HEADERS          = "Host:${var.auth_fqdn},X-Forwarded-Proto:https"
    } : { name = k, value = v }]

    portMappings = [{ containerPort = 3000, protocol = "tcp" }]

    mountPoints = [{
      sourceVolume  = "zitadel-bootstrap"
      containerPath = local.zitadel_bootstrap_path
      readOnly      = true
    }]

    healthCheck = {
      command     = ["CMD", "/bin/sh", "-c", "node /app/healthcheck.mjs http://localhost:3000/ui/v2/login/healthy"]
      interval    = 15
      timeout     = 5
      retries     = 5
      startPeriod = 60
    }
  }])

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Target groups
# ------------------------------------------------------------------------------
resource "aws_lb_target_group" "zitadel_api" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}-zitadel"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/debug/ready"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

resource "aws_lb_target_group" "zitadel_login" {
  count       = local.zitadel_enabled ? 1 : 0
  name        = "${var.name_prefix}-zitadel-login"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/ui/v2/login/healthy"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# ALB host-based routing on auth.<zone>:
#   /ui/v2/login* -> Login UI (lower priority number = evaluated first)
#   everything else on the host -> Zitadel API/console
# ------------------------------------------------------------------------------
resource "aws_lb_listener_rule" "zitadel_login" {
  count        = local.zitadel_enabled ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 150

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.zitadel_login[0].arn
  }

  condition {
    host_header {
      values = [var.auth_fqdn]
    }
  }

  condition {
    path_pattern {
      values = ["/ui/v2/login*"]
    }
  }

  tags = var.tags
}

resource "aws_lb_listener_rule" "zitadel_api" {
  count        = local.zitadel_enabled ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 160

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.zitadel_api[0].arn
  }

  condition {
    host_header {
      values = [var.auth_fqdn]
    }
  }

  tags = var.tags
}

# Open the Zitadel container ports to the ALB (the shared ECS SG only opens the
# API container port by default).
resource "aws_security_group_rule" "zitadel_api_from_alb" {
  count                    = local.zitadel_enabled ? 1 : 0
  type                     = "ingress"
  description              = "Zitadel API from ALB"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.alb_security_group_id
}

resource "aws_security_group_rule" "zitadel_login_from_alb" {
  count                    = local.zitadel_enabled ? 1 : 0
  type                     = "ingress"
  description              = "Zitadel Login UI from ALB"
  from_port                = 3000
  to_port                  = 3000
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.alb_security_group_id
}

# Login UI -> Zitadel API on 8080, task-to-task within the shared ECS SG.
resource "aws_security_group_rule" "zitadel_intra_ecs" {
  count                    = local.zitadel_enabled ? 1 : 0
  type                     = "ingress"
  description              = "Zitadel Login UI to Zitadel API (task-to-task)"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.ecs_security_group_id
}

# ------------------------------------------------------------------------------
# Services
# ------------------------------------------------------------------------------
# ECS Exec on the Zitadel API task lets an operator read the first-boot admin PAT
# (/zitadel/bootstrap/admin.pat) once and seed it into Secrets Manager. Requires
# the ssmmessages channel actions on the task role.
data "aws_iam_policy_document" "zitadel_exec" {
  count = local.zitadel_enabled ? 1 : 0
  statement {
    sid = "ECSExecSSMMessages"
    actions = [
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "zitadel_exec" {
  count  = local.zitadel_enabled ? 1 : 0
  name   = "${var.name_prefix}-zitadel-exec"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.zitadel_exec[0].json
}

resource "aws_ecs_service" "zitadel" {
  count                  = local.zitadel_enabled ? 1 : 0
  name                   = "${var.name_prefix}-zitadel"
  cluster                = aws_ecs_cluster.this.id
  task_definition        = aws_ecs_task_definition.zitadel[0].arn
  desired_count          = 1
  launch_type            = "FARGATE"
  enable_execute_command = true

  health_check_grace_period_seconds = 180

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.zitadel_api[0].arn
    container_name   = "zitadel"
    container_port   = 8080
  }

  service_registries {
    registry_arn = aws_service_discovery_service.zitadel[0].arn
  }

  depends_on = [aws_lb_listener.https, aws_efs_mount_target.zitadel]

  tags = var.tags
}

resource "aws_ecs_service" "zitadel_login" {
  count           = local.zitadel_enabled ? 1 : 0
  name            = "${var.name_prefix}-zitadel-login"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.zitadel_login[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 120

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.zitadel_login[0].arn
    container_name   = "zitadel-login"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.https, aws_ecs_service.zitadel]

  tags = var.tags
}
