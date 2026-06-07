# Always-on ingestion service: Dagster daemon + webserver in one ECS task.
# Workflows run inside this container (Meltano subprocesses via the orchestrator).

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
    name        = "ingestion"
    image       = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential   = true
    command     = ["ingestion"]
    environment = [for k, v in merge(var.app_environment, {
      SKIP_MIGRATIONS   = "1"
      DAGSTER_HOME      = "/app/dagster_home"
      OTEL_SERVICE_NAME = "propel-ingestion"
    }) : { name = k, value = v }]
    secrets = local.container_secrets
    portMappings = [{
      containerPort = 3000
      protocol      = "tcp"
    }]
  }])

  tags = var.tags
}

resource "aws_ecs_service" "ingestion" {
  count           = var.ingestion_enabled ? 1 : 0
  name            = "${var.name_prefix}-ingestion"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.ingestion[0].arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  tags = var.tags
}
