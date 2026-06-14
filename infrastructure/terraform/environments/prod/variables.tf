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

variable "dagster_subdomain" {
  type        = string
  default     = "dagster"
  description = "Subdomain label for the Dagster ingestion UI."
}

variable "auth_subdomain" {
  type        = string
  default     = "auth"
  description = "Subdomain label for the Zitadel identity provider."
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
  description = "Provision the long-running Dagster ingestion ECS service + UI."
}

variable "dagster_allowed_cidrs" {
  type        = list(string)
  default     = []
  description = "Source IP CIDRs allowed to reach the Dagster UI. Empty = open (no auth)."
}

variable "zitadel_enabled" {
  type        = bool
  default     = false
  description = "Host the single shared Zitadel instance behind auth.<zone> (prod owns it). Default false until the first apply that stands it up; set true to provision."
}

variable "zitadel_mgmt_token" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Zitadel IAM_OWNER PAT for deploy-zitadel.sh, seeded into propel-prod/zitadel/MGMT_TOKEN. Empty keeps the placeholder so the first-boot EFS PAT is not clobbered."
}
