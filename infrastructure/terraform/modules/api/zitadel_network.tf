# ------------------------------------------------------------------------------
# Zitadel networking (see zitadel.tf for the module overview): service discovery,
# ALB target groups + host-based listener rules on auth.<zone>, and the ECS
# security-group rules that open the container ports.
# ------------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# Service discovery: the Login UI resolves the Zitadel API at
# zitadel.<name_prefix>-auth.local (registered by the zitadel ECS service).
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

# Dagster (ingestion.tf) already opens this same ALB -> ECS :3000 rule when
# dagster_port is 3000. AWS rejects duplicate SG rules even with different
# descriptions, so only add it here when ingestion is not using that port.
resource "aws_security_group_rule" "zitadel_login_from_alb" {
  count                    = local.zitadel_enabled && !(var.ingestion_enabled && var.dagster_port == 3000) ? 1 : 0
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
