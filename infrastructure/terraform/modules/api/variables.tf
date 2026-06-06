variable "name_prefix" {
  type        = string
  description = "Prefix for named resources, e.g. propel-beta."
}

variable "vpc_id" {
  type        = string
  description = "VPC the ALB and target group live in."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the ALB."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the ECS tasks."
}

variable "alb_security_group_id" {
  type        = string
  description = "Security group for the ALB."
}

variable "ecs_security_group_id" {
  type        = string
  description = "Security group for the ECS tasks."
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM certificate ARN (us-east-1) covering the API FQDN."
}

variable "database_url_secret_arn" {
  type        = string
  description = "Secrets Manager ARN holding the DATABASE_URL."
}

variable "app_environment" {
  type        = map(string)
  description = "Plain environment variables injected into the API container (e.g. forwarded from GitHub Actions variables: POSTHOG_TOKEN, POSTHOG_HOST, ...)."
  default     = {}
}

variable "app_secrets" {
  type        = map(string)
  description = "Sensitive key/value pairs stored in Secrets Manager and injected into the API container."
  default     = {}
  sensitive   = true
}

variable "container_port" {
  type        = number
  description = "Port the FastAPI container listens on."
  default     = 8000
}

variable "health_check_path" {
  type        = string
  description = "ALB target group health check path."
  default     = "/health"
}

variable "image_tag" {
  type        = string
  description = "ECR image tag the service runs."
  default     = "latest"
}

variable "desired_count" {
  type        = number
  description = "Number of API tasks (no autoscaling; fixed)."
  default     = 1
}

variable "task_cpu" {
  type        = number
  description = "Fargate task CPU units."
  default     = 256
}

variable "task_memory" {
  type        = number
  description = "Fargate task memory (MiB)."
  default     = 512
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}
