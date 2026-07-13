# CloudWatch alarms + ECS deployment circuit breaker for metric-driven rollbacks.
#
# During an active ECS deployment, Amazon ECS watches these ALB target-group
# metrics. If an alarm enters ALARM (or the circuit breaker trips on task/ELB
# health failures), ECS automatically rolls the service back to the last
# successful task-definition revision.
#
# App logs still go to PostHog — these are deploy-safety metrics only.

locals {
  # CloudWatch ALB dimensions use the ARN suffix forms ``app/...`` and
  # ``targetgroup/...``.
  api_tg_dimension = regex("targetgroup/.+$", aws_lb_target_group.api.arn)
  alb_arn_suffix   = regex("app/.+$", aws_lb.this.arn)
}

# ------------------------------------------------------------------------------
# Release SHA tracking (used by deploy/rollback scripts + metric-rollback Lambda)
# ------------------------------------------------------------------------------

resource "aws_ssm_parameter" "release_current" {
  name        = "/${var.name_prefix}/release/current"
  description = "Git SHA of the currently live API/SPA release."
  type        = "String"
  value       = "none"

  lifecycle {
    ignore_changes = [value]
  }

  tags = var.tags
}

resource "aws_ssm_parameter" "release_previous" {
  name        = "/${var.name_prefix}/release/previous"
  description = "Git SHA of the previous successful release (metric / manual rollback target)."
  type        = "String"
  value       = "none"

  lifecycle {
    ignore_changes = [value]
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Deploy-safety alarms (ALB / target-group metrics — no Container Insights)
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "api_unhealthy_hosts" {
  alarm_name          = "${var.name_prefix}-api-unhealthy-hosts"
  alarm_description   = "API target group has unhealthy hosts (triggers ECS deploy rollback)."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = local.alb_arn_suffix
    TargetGroup  = local.api_tg_dimension
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "api_target_5xx" {
  alarm_name          = "${var.name_prefix}-api-target-5xx"
  alarm_description   = "API targets returning 5xx (triggers ECS deploy rollback)."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = local.alb_arn_suffix
    TargetGroup  = local.api_tg_dimension
  }

  tags = var.tags
}
