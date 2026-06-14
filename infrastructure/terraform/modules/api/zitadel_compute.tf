# ------------------------------------------------------------------------------
# Zitadel compute (see zitadel.tf for the module overview): the shared EFS
# bootstrap volume, the two ECS task definitions/services, and the ECS Exec IAM
# policy used to read the first-boot admin PAT. Only created where the Zitadel
# containers run (zitadel_enabled).
# ------------------------------------------------------------------------------

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
# Services
# ------------------------------------------------------------------------------
# ECS Exec lets an operator read the first-boot admin PAT
# (/zitadel/bootstrap/admin.pat) once and seed it into Secrets Manager. The
# zitadel API image is distroless, so the readable path is exec'ing into the
# login container (which has a shell and mounts the same EFS volume); both
# services share this task role. Requires the ssmmessages channel actions.
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
  # The zitadel API image is distroless (no shell/coreutils), so the first-boot
  # admin PAT on the shared EFS volume can only be read by exec'ing into the
  # login container, which ships a shell. See docs/deployment/zitadel.md.
  enable_execute_command = true

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
