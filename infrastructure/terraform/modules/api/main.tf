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

# ------------------------------------------------------------------------------
# Container registry
# ------------------------------------------------------------------------------
resource "aws_ecr_repository" "api" {
  name                 = "${var.name_prefix}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# ------------------------------------------------------------------------------
# BFF session cookie signing secret — generated on first apply (same pattern as
# the DB password). Stored in Secrets Manager; never passed through CI.
# ------------------------------------------------------------------------------
moved {
  from = random_password.jwt_secret
  to   = random_password.session_secret
}

moved {
  from = aws_secretsmanager_secret.jwt_secret
  to   = aws_secretsmanager_secret.session_secret
}

moved {
  from = aws_secretsmanager_secret_version.jwt_secret
  to   = aws_secretsmanager_secret_version.session_secret
}

resource "random_password" "session_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "session_secret" {
  name        = "${var.name_prefix}/app/SESSION_SECRET"
  description = "BFF session cookie signing secret for the ${var.name_prefix} API."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "session_secret" {
  secret_id     = aws_secretsmanager_secret.session_secret.id
  secret_string = random_password.session_secret.result

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# ------------------------------------------------------------------------------
# External application secrets (OAuth client secrets, Zitadel OIDC, etc.). Each
# entry in var.app_secrets becomes a Secrets Manager secret injected into the
# task. SESSION_SECRET is managed separately above — do not pass it here.
# ------------------------------------------------------------------------------
locals {
  external_app_secrets = {
    for key, value in var.app_secrets : key => value
    if !contains(["JWT_SECRET", "SESSION_SECRET"], key)
  }

  # Secrets injected into every task that runs the app (API service + the
  # scheduled ingestion task), so both share one source of truth.
  container_secrets = concat(
    [{ name = "DATABASE_URL", valueFrom = var.database_url_secret_arn }],
    [{ name = "SESSION_SECRET", valueFrom = aws_secretsmanager_secret.session_secret.arn }],
    [for k in nonsensitive(keys(local.external_app_secrets)) : { name = k, valueFrom = aws_secretsmanager_secret.app[k].arn }],
    # OIDC client id/secret are Terraform-managed placeholders overwritten by the
    # Zitadel bootstrap step (see zitadel.tf); injected in every environment that
    # consumes Zitadel (beta consumes the shared prod instance).
    local.zitadel_consumer ? [
      { name = "ZITADEL_CLIENT_ID", valueFrom = aws_secretsmanager_secret.zitadel_client_id[0].arn },
      { name = "ZITADEL_CLIENT_SECRET", valueFrom = aws_secretsmanager_secret.zitadel_client_secret[0].arn },
    ] : [],
  )
}

resource "aws_secretsmanager_secret" "app" {
  for_each    = toset(nonsensitive(keys(local.external_app_secrets)))
  name        = "${var.name_prefix}/app/${each.key}"
  description = "App secret ${each.key} for ${var.name_prefix}."
  tags        = var.tags
}

resource "aws_secretsmanager_secret_version" "app" {
  for_each      = toset(nonsensitive(keys(local.external_app_secrets)))
  secret_id     = aws_secretsmanager_secret.app[each.key].id
  secret_string = local.external_app_secrets[each.key]
}

# ------------------------------------------------------------------------------
# IAM
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Execution role: pull from ECR + read the two secrets. Intentionally NO
# CloudWatch Logs permissions (the task has no logConfiguration).
resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-ecs-exec"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "execution" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPull"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [aws_ecr_repository.api.arn]
  }
  statement {
    sid     = "ReadSecrets"
    actions = ["secretsmanager:GetSecretValue"]
    resources = concat(
      [var.database_url_secret_arn],
      [aws_secretsmanager_secret.session_secret.arn],
      [for s in aws_secretsmanager_secret.app : s.arn],
    )
  }
}

resource "aws_iam_role_policy" "execution" {
  name   = "${var.name_prefix}-ecs-exec"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution.json
}

# Task role: app identity. No AWS permissions required today (DB over the
# network, PostHog over HTTPS); kept for future use.
resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

# ------------------------------------------------------------------------------
# ECS cluster + task + service
# ------------------------------------------------------------------------------
resource "aws_ecs_cluster" "this" {
  name = var.name_prefix

  # Container Insights pushes metrics to CloudWatch; disabled by design.
  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = var.tags
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    # No logConfiguration on purpose: no CloudWatch. Observability is shipped
    # to PostHog by the app itself (OpenTelemetry traces).
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]
    environment = [for k, v in var.app_environment : { name = k, value = v }]
    secrets     = local.container_secrets
  }])

  tags = var.tags
}

resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 60

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.https]

  # Task definition revisions are registered by Terraform (env/cpu/secrets) but
  # rolled out by scripts/deploy-api.sh, which runs only after the Zitadel
  # bootstrap step has populated the OIDC client secrets. Without this, a plain
  # terraform apply would roll the API onto placeholder OIDC creds.
  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Application Load Balancer
# ------------------------------------------------------------------------------
resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids
  tags               = var.tags
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
