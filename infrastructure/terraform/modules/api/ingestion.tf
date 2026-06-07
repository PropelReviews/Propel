# ------------------------------------------------------------------------------
# Scheduled ingestion (V1): an EventBridge Scheduler invokes a one-shot Fargate
# task hourly that runs `python -m app.ingestion.cli run` and exits. Same image
# and secrets as the API; no always-on container. Gated by var.ingestion_enabled
# so environments opt in.
# ------------------------------------------------------------------------------

resource "aws_ecs_task_definition" "ingestion" {
  count                    = var.ingestion_enabled ? 1 : 0
  family                   = "${var.name_prefix}-ingestion"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ingestion_task_cpu
  memory                   = var.ingestion_task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "ingestion"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    # One-shot run, then exit (the schedule re-invokes hourly). SKIP_MIGRATIONS
    # keeps schema changes owned by the API deploy, not the ingestion task.
    command     = ["python", "-m", "app.ingestion.cli", "run"]
    environment = [for k, v in merge(var.app_environment, { SKIP_MIGRATIONS = "1" }) : { name = k, value = v }]
    secrets     = local.container_secrets
  }])

  tags = var.tags
}

# IAM role assumed by EventBridge Scheduler to launch the task.
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  count              = var.ingestion_enabled ? 1 : 0
  name               = "${var.name_prefix}-ingestion-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "scheduler" {
  count = var.ingestion_enabled ? 1 : 0

  statement {
    sid     = "RunIngestionTask"
    actions = ["ecs:RunTask"]
    # Any revision of the ingestion task family.
    resources = ["${aws_ecs_task_definition.ingestion[0].arn_without_revision}:*"]
    condition {
      test     = "ArnLike"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.this.arn]
    }
  }

  # Scheduler must pass the task's execution + task roles to ECS.
  statement {
    sid       = "PassTaskRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.task.arn]
    condition {
      test     = "StringLike"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "scheduler" {
  count  = var.ingestion_enabled ? 1 : 0
  name   = "${var.name_prefix}-ingestion-scheduler"
  role   = aws_iam_role.scheduler[0].id
  policy = data.aws_iam_policy_document.scheduler[0].json
}

resource "aws_scheduler_schedule" "ingestion" {
  count = var.ingestion_enabled ? 1 : 0
  name  = "${var.name_prefix}-ingestion"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.ingestion_schedule_expression
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.this.arn
    role_arn = aws_iam_role.scheduler[0].arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.ingestion[0].arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        subnets          = var.private_subnet_ids
        security_groups  = [var.ecs_security_group_id]
        assign_public_ip = false
      }
    }

    # The orchestrator is idempotent and self-heals next hour; don't pile up
    # retries of a failed run.
    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}
