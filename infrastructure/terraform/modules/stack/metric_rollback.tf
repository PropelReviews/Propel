# Metric-driven full-stack rollback companion to the API ECS circuit breaker.
#
# When ECS marks a deployment FAILED (circuit breaker or CloudWatch deploy
# alarms), EventBridge invokes a Lambda that:
#   1. Reads the previous release SHA from SSM
#   2. Re-pins API / ingestion / Dask to that ECR image
#   3. Restores frontend + landing from s3://…/releases/<sha>/
#   4. Publishes an SNS notification

data "archive_file" "metric_rollback" {
  type        = "zip"
  source_file = "${path.module}/lambda/metric_rollback.py"
  output_path = "${path.module}/.build/metric_rollback.zip"
}

resource "aws_sns_topic" "deploy_rollback" {
  name = "${var.name_prefix}-deploy-rollback"
  tags = var.tags
}

resource "aws_iam_role" "metric_rollback" {
  name = "${var.name_prefix}-metric-rollback"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "metric_rollback" {
  name = "metric-rollback"
  role = aws_iam_role.metric_rollback.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Logs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/lambda/${var.name_prefix}-metric-rollback*"
      },
      {
        Sid    = "SsmRelease"
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:PutParameter"]
        Resource = [
          "arn:aws:ssm:*:*:parameter${module.api.release_current_parameter}",
          "arn:aws:ssm:*:*:parameter${module.api.release_previous_parameter}",
        ]
      },
      {
        Sid    = "EcsRollback"
        Effect = "Allow"
        Action = [
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeServices",
        ]
        Resource = "*"
      },
      {
        Sid      = "PassEcsRoles"
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = "arn:aws:iam::*:role/${var.name_prefix}-*"
      },
      {
        Sid    = "S3Restore"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          module.frontend.bucket_arn,
          "${module.frontend.bucket_arn}/*",
          module.landing.bucket_arn,
          "${module.landing.bucket_arn}/*",
        ]
      },
      {
        Sid      = "CloudFrontInvalidate"
        Effect   = "Allow"
        Action   = ["cloudfront:CreateInvalidation"]
        Resource = "*"
      },
      {
        Sid      = "SnsNotify"
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.deploy_rollback.arn
      },
    ]
  })
}

resource "aws_lambda_function" "metric_rollback" {
  function_name = "${var.name_prefix}-metric-rollback"
  role          = aws_iam_role.metric_rollback.arn
  handler       = "metric_rollback.handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 256

  filename         = data.archive_file.metric_rollback.output_path
  source_code_hash = data.archive_file.metric_rollback.output_base64sha256

  environment {
    variables = {
      CURRENT_SHA_PARAM        = module.api.release_current_parameter
      PREVIOUS_SHA_PARAM       = module.api.release_previous_parameter
      SNS_TOPIC_ARN            = aws_sns_topic.deploy_rollback.arn
      ECS_CLUSTER              = module.api.cluster_name
      API_SERVICE              = module.api.service_name
      INGESTION_SERVICE        = coalesce(module.api.ingestion_service_name, "")
      DASK_WORKER_SERVICE      = coalesce(module.api.dask_worker_service_name, "")
      ECR_REPOSITORY_URL       = module.api.ecr_repository_url
      FRONTEND_BUCKET          = module.frontend.bucket_name
      FRONTEND_DISTRIBUTION_ID = module.frontend.distribution_id
      LANDING_BUCKET           = module.landing.bucket_name
      LANDING_DISTRIBUTION_ID  = module.landing.distribution_id
      API_HEALTH_URL           = "https://${var.api_fqdn}/health"
    }
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "ecs_deployment_failed" {
  name        = "${var.name_prefix}-ecs-deploy-failed"
  description = "ECS SERVICE_DEPLOYMENT_FAILED for ${var.name_prefix} (circuit breaker / deploy alarms)"

  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Deployment State Change"]
    detail = {
      eventName  = ["SERVICE_DEPLOYMENT_FAILED"]
      clusterArn = [module.api.cluster_arn]
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "metric_rollback" {
  rule      = aws_cloudwatch_event_rule.ecs_deployment_failed.name
  target_id = "metric-rollback"
  arn       = aws_lambda_function.metric_rollback.arn
}

resource "aws_lambda_permission" "metric_rollback_events" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metric_rollback.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ecs_deployment_failed.arn
}

# Sustained post-deploy metric failure: if the API stays unhealthy after the
# deployment window, still roll back to the previous SHA.
resource "aws_cloudwatch_metric_alarm" "api_unhealthy_sustained" {
  alarm_name          = "${var.name_prefix}-api-unhealthy-sustained"
  alarm_description   = "API unhealthy for 10+ minutes — trigger full metric rollback to previous SHA."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 5
  datapoints_to_alarm = 5
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 120
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.deploy_rollback.arn]

  dimensions = {
    LoadBalancer = regex("app/.+$", module.api.alb_arn)
    TargetGroup  = regex("targetgroup/.+$", module.api.target_group_arn)
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "api_unhealthy_sustained" {
  name        = "${var.name_prefix}-api-unhealthy-sustained"
  description = "Sustained API unhealthy alarm → metric rollback Lambda"

  event_pattern = jsonencode({
    source        = ["aws.cloudwatch"]
    "detail-type" = ["CloudWatch Alarm State Change"]
    detail = {
      alarmName = [aws_cloudwatch_metric_alarm.api_unhealthy_sustained.alarm_name]
      state = {
        value = ["ALARM"]
      }
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "api_unhealthy_sustained" {
  rule      = aws_cloudwatch_event_rule.api_unhealthy_sustained.name
  target_id = "metric-rollback-sustained"
  arn       = aws_lambda_function.metric_rollback.arn
}

resource "aws_lambda_permission" "metric_rollback_sustained" {
  statement_id  = "AllowEventBridgeSustained"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metric_rollback.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.api_unhealthy_sustained.arn
}
