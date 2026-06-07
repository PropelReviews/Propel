variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Deployment region (also where the CloudFront ACM cert must live)."
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Environment name; used in resource prefixes and tags."
}

variable "zone_name" {
  type        = string
  default     = "propel.ninja"
  description = "Existing Route53 hosted zone for prod (manual prereq)."
}

variable "api_subdomain" {
  type    = string
  default = "api"
}

variable "app_subdomain" {
  type    = string
  default = "app"
}

variable "beta_zone_name" {
  type        = string
  default     = "beta.propel.ninja"
  description = "Child zone delegated from the prod zone."
}

variable "beta_dns_role_arn" {
  type        = string
  default     = "arn:aws:iam::536270449640:role/PropelTerraform"
  description = "Role in the beta account assumed (read-only) to read the beta zone NS."
}

variable "db_min_acu" {
  type    = number
  default = 0.5
}

variable "db_max_acu" {
  type    = number
  default = 4
}

variable "api_image_tag" {
  type        = string
  default     = "latest"
  description = "ECR image tag the API service runs."
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "app_environment" {
  type        = map(string)
  default     = {}
  description = "Plain env vars for the API container. CI forwards all GitHub Actions variables here (e.g. POSTHOG_TOKEN, POSTHOG_HOST)."
}

variable "app_secrets" {
  type        = map(string)
  default     = {}
  sensitive   = true
  description = "Sensitive key/value pairs stored in Secrets Manager and injected into the API container."
}

variable "ingestion_enabled" {
  type        = bool
  default     = true
  description = "Provision the always-on Dagster ingestion ECS service."
}
