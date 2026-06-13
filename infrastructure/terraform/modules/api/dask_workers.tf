# ------------------------------------------------------------------------------
# Dask worker fleet: scale-to-zero distributed compute for ingestion.
#
# org_ingestion_job runs submit their steps (Meltano extractions) to a Dask
# scheduler embedded in the ingestion task (entrypoint `dagster-service` with
# DASK_SCHEDULER_EMBEDDED=1); this fleet executes them. The service is declared
# with desired_count = 0 and scaled by the Dagster coordinator itself
# (orchestration/propel_orchestration/worker_scaling.py): up to
# dask_worker_max_count when org runs queue, back to zero when idle. No
# CloudWatch/Application Auto Scaling, in keeping with the stack's design.
#
# Service discovery: workers and run tasks find the scheduler via a Cloud Map
# private DNS name (dask-scheduler.<name_prefix>.local) that the ingestion
# service registers its task IP under.
# ------------------------------------------------------------------------------

locals {
  dask_enabled           = var.ingestion_enabled && var.dask_enabled
  dask_namespace_name    = "${var.name_prefix}.local"
  dask_scheduler_address = "tcp://dask-scheduler.${local.dask_namespace_name}:8786"
  dask_worker_service    = "${var.name_prefix}-dask-workers"
}

resource "aws_service_discovery_private_dns_namespace" "this" {
  count       = local.dask_enabled ? 1 : 0
  name        = local.dask_namespace_name
  description = "Private service discovery for ${var.name_prefix} (Dask scheduler)."
  vpc         = var.vpc_id
  tags        = var.tags
}

# DNS name for the embedded scheduler; the ingestion ECS service registers its
# task IP here (see service_registries in ingestion.tf).
resource "aws_service_discovery_service" "dask_scheduler" {
  count = local.dask_enabled ? 1 : 0
  name  = "dask-scheduler"

  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.this[0].id
    routing_policy = "MULTIVALUE"
    dns_records {
      type = "A"
      ttl  = 10
    }
  }

  # Do not set health_check_custom_config here — adding or changing it forces
  # replacement of this resource, which fails while the ingestion task is
  # registered. AWS defaults are fine; ignore drift if the API returns one.
  lifecycle {
    ignore_changes = [health_check_custom_config]
  }

  tags = var.tags
}

# Dask needs free task-to-task TCP inside the cluster: workers dial the
# scheduler on 8786, the scheduler dials workers back, and run-task clients
# gather step results from workers on ephemeral ports. Everything shares the
# one ECS security group, so a single self-referencing rule covers all of it
# (the group previously had no ECS-to-ECS ingress at all).
resource "aws_security_group_rule" "dask_intra_ecs" {
  count                    = local.dask_enabled ? 1 : 0
  type                     = "ingress"
  description              = "Dask scheduler/worker/client comms between ECS tasks"
  from_port                = 0
  to_port                  = 65535
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.ecs_security_group_id
}

resource "aws_ecs_task_definition" "dask_worker" {
  count                    = local.dask_enabled ? 1 : 0
  family                   = local.dask_worker_service
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.dask_worker_cpu
  memory                   = var.dask_worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "dask-worker"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    # entrypoint.sh: connects to DASK_SCHEDULER_ADDRESS and runs
    # DASK_WORKER_PROCESSES single-threaded worker processes.
    command = ["dask-worker"]

    # Steps import the full app (DB, GitHub App creds) and shell out to
    # Meltano, so workers carry the same env + secrets as the ingestion task.
    environment = [for k, v in merge(var.app_environment, {
      SKIP_MIGRATIONS        = "1"
      OTEL_SERVICE_NAME      = "propel-ingestion"
      DAGSTER_HOME           = "/tmp/dagster"
      DASK_SCHEDULER_ADDRESS = local.dask_scheduler_address
      DASK_WORKER_PROCESSES  = tostring(var.dask_worker_processes)
    }) : { name = k, value = v }]
    secrets = local.container_secrets

    healthCheck = {
      command     = ["CMD-SHELL", "pgrep -f 'dask worker' > /dev/null || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 120
    }
  }])

  tags = var.tags
}

resource "aws_ecs_service" "dask_workers" {
  count           = local.dask_enabled ? 1 : 0
  name            = local.dask_worker_service
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dask_worker[0].arn
  desired_count   = 0
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  # The Dagster coordinator owns desired_count (scale up on fan-out, down to 0
  # when idle); terraform must not reset it on every apply. Task definition
  # rollouts are handled by scripts/deploy-api.sh (same as ingestion).
  lifecycle {
    ignore_changes = [desired_count, task_definition]
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# IAM: the coordinator's task role launches runs (EcsRunLauncher) and scales
# the worker fleet (worker_scaling.py). Scoped where the APIs allow it.
# ------------------------------------------------------------------------------
data "aws_iam_policy_document" "dagster_orchestration" {
  count = var.ingestion_enabled ? 1 : 0

  # EcsRunLauncher: register a derived task definition per deploy and run/stop
  # one task per Dagster run. RunTask/Describe/Stop operate on dynamically
  # created task definition families, so they cannot be resource-scoped.
  statement {
    sid = "EcsRunLauncher"
    actions = [
      "ecs:DescribeTaskDefinition",
      "ecs:DescribeTasks",
      "ecs:ListAccountSettings",
      "ecs:ListTagsForResource",
      "ecs:RegisterTaskDefinition",
      "ecs:RunTask",
      "ecs:StopTask",
      "ecs:TagResource",
    ]
    resources = ["*"]
  }

  # The launcher resolves the awsvpc network config of the current task.
  statement {
    sid       = "DescribeNetworking"
    actions   = ["ec2:DescribeNetworkInterfaces"]
    resources = ["*"]
  }

  # Launched run tasks reuse the same execution/task roles.
  statement {
    sid     = "PassTaskRoles"
    actions = ["iam:PassRole"]
    resources = [
      aws_iam_role.execution.arn,
      aws_iam_role.task.arn,
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  # Worker fleet autoscaling (Dagster sensors -> desired_count).
  dynamic "statement" {
    for_each = local.dask_enabled ? [1] : []
    content {
      sid = "ScaleDaskWorkers"
      actions = [
        "ecs:DescribeServices",
        "ecs:UpdateService",
      ]
      resources = [aws_ecs_service.dask_workers[0].id]
    }
  }
}

resource "aws_iam_role_policy" "dagster_orchestration" {
  count  = var.ingestion_enabled ? 1 : 0
  name   = "${var.name_prefix}-dagster-orchestration"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.dagster_orchestration[0].json
}
