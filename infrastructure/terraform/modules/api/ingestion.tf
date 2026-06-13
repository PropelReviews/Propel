# ------------------------------------------------------------------------------
# Ingestion (V2): a long-running Dagster service on ECS Fargate. One always-on
# task runs the Dagster daemon (hourly schedule -> `orchestrator.run_all`) plus
# the Dagster webserver, served at dagster.<zone> through the shared ALB. Same
# image and secrets as the API. Gated by var.ingestion_enabled so environments
# opt in.
#
# NOTE: Dagster OSS has no built-in auth. The UI is reachable by anyone who knows
# the URL; restrict at the network layer (security group / WAF / VPN) as a
# follow-up if needed.
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
    # `dagster-service` makes entrypoint.sh start the daemon + webserver. The
    # daemon owns the hourly schedule; SKIP_MIGRATIONS keeps the app schema owned
    # by the API deploy (Dagster manages its own tables in a separate schema).
    command = ["dagster-service"]
    environment = [for k, v in merge(
      var.app_environment,
      {
        SKIP_MIGRATIONS   = "1"
        OTEL_SERVICE_NAME = "propel-ingestion"
        DAGSTER_HOME      = "/tmp/dagster"
        DAGSTER_PORT      = tostring(var.dagster_port)
        # EcsRunLauncher reads this from the code location metadata when
        # dequeuing runs (required since Dagster 1.9.x). Must match the image
        # this task is running.
        DAGSTER_CURRENT_IMAGE = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      },
      # Dask: embedded scheduler on this task (entrypoint starts it next to
      # the daemon), runs as their own Fargate tasks (EcsRunLauncher), worker
      # fleet autoscaled by the coordinator (worker_scaling.py).
      local.dask_enabled ? {
        DASK_SCHEDULER_EMBEDDED = "1"
        DASK_SCHEDULER_ADDRESS  = local.dask_scheduler_address
        DAGSTER_RUN_LAUNCHER    = "ecs"
        DASK_WORKER_ECS_CLUSTER = aws_ecs_cluster.this.name
        DASK_WORKER_ECS_SERVICE = local.dask_worker_service
        DASK_WORKER_MAX         = tostring(var.dask_worker_max_count)
      } : {},
    ) : { name = k, value = v }]
    secrets = local.container_secrets

    portMappings = concat(
      [{
        containerPort = var.dagster_port
        protocol      = "tcp"
      }],
      # Dask scheduler RPC + dashboard (reachable only inside the ECS SG).
      local.dask_enabled ? [
        { containerPort = 8786, protocol = "tcp" },
        { containerPort = 8787, protocol = "tcp" },
      ] : [],
    )

    # Liveness: the daemon must be running for schedules to fire. Generous
    # startPeriod covers Meltano/Dagster warmup on a cold task.
    healthCheck = {
      command     = ["CMD-SHELL", "pgrep -f dagster-daemon > /dev/null && pgrep -f 'dagster api grpc' > /dev/null || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 180
    }
  }])

  tags = var.tags
}

# Dagster webserver target group (HTTP on the Dagster port). `/server_info`
# returns 200 once the webserver is up.
resource "aws_lb_target_group" "ingestion" {
  count       = var.ingestion_enabled ? 1 : 0
  name        = "${var.name_prefix}-dagster"
  port        = var.dagster_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/server_info"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

# Host-based routing on the existing HTTPS listener: dagster.<zone> -> Dagster.
# When dagster_allowed_cidrs is set, the forward only matches those source IPs;
# all other clients for this host fall through to the 403 rule below. Dagster OSS
# has no auth, so this IP allowlist is the access control.
resource "aws_lb_listener_rule" "ingestion" {
  count        = var.ingestion_enabled ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ingestion[0].arn
  }

  condition {
    host_header {
      values = [var.dagster_fqdn]
    }
  }

  # ALB evaluates source_ip against the client IP as seen by the load balancer
  # (the public egress IP, not any X-Forwarded-For). Only added when an allowlist
  # is configured; otherwise the UI is open.
  dynamic "condition" {
    for_each = length(var.dagster_allowed_cidrs) > 0 ? [1] : []
    content {
      source_ip {
        values = var.dagster_allowed_cidrs
      }
    }
  }

  tags = var.tags
}

# Catch-all for the Dagster host: any client not in the allowlist gets 403.
# Higher priority number => evaluated after the forward rule above.
resource "aws_lb_listener_rule" "ingestion_deny" {
  count        = var.ingestion_enabled && length(var.dagster_allowed_cidrs) > 0 ? 1 : 0
  listener_arn = aws_lb_listener.https.arn
  priority     = 101

  action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }

  condition {
    host_header {
      values = [var.dagster_fqdn]
    }
  }

  tags = var.tags
}

# Allow the ALB to reach the Dagster webserver port on the ECS tasks (the shared
# ECS security group only opens the API container port by default).
resource "aws_security_group_rule" "ingestion_from_alb" {
  count                    = var.ingestion_enabled ? 1 : 0
  type                     = "ingress"
  description              = "Dagster webserver from ALB"
  from_port                = var.dagster_port
  to_port                  = var.dagster_port
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = var.alb_security_group_id
}

resource "aws_ecs_service" "ingestion" {
  count           = var.ingestion_enabled ? 1 : 0
  name            = "${var.name_prefix}-ingestion"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.ingestion[0].arn
  desired_count   = var.ingestion_desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 180

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ingestion[0].arn
    container_name   = "ingestion"
    container_port   = var.dagster_port
  }

  # Register the task IP as dask-scheduler.<name_prefix>.local so workers and
  # run tasks can reach the embedded Dask scheduler.
  dynamic "service_registries" {
    for_each = local.dask_enabled ? [1] : []
    content {
      registry_arn = aws_service_discovery_service.dask_scheduler[0].arn
    }
  }

  depends_on = [aws_lb_listener.https]

  # Task definition revisions are registered by Terraform (env/cpu/secrets)
  # but rolled out by scripts/deploy-api.sh (one register+update per deploy).
  # Without this, terraform apply and deploy-api both trigger a rollout.
  lifecycle {
    ignore_changes = [task_definition]
  }

  tags = var.tags
}
