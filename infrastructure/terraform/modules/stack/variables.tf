variable "name_prefix" {
  type        = string
  description = "Prefix for named resources, e.g. propel-beta."
}

variable "zone_id" {
  type        = string
  description = "Route53 hosted zone ID for this environment's domain."
}

variable "zone_name" {
  type        = string
  description = "Route53 hosted zone apex FQDN (e.g. beta.propel.ninja). Used for relative record names."
}

variable "api_fqdn" {
  type        = string
  description = "API FQDN, e.g. api.beta.propel.ninja."
}

variable "app_fqdn" {
  type        = string
  description = "Frontend FQDN, e.g. app.beta.propel.ninja."
}

variable "landing_fqdns" {
  type        = list(string)
  description = "Landing site FQDNs (apex + www), e.g. [\"propel.ninja\", \"www.propel.ninja\"]. The first entry is treated as the canonical apex."
}

variable "landing_dns_fqdns" {
  type        = list(string)
  default     = null
  description = "FQDNs to create Route53 landing alias records for. Defaults to landing_fqdns. Set to the apex only when www is managed cross-account from prod (beta env)."
}

variable "container_port" {
  type        = number
  description = "FastAPI container port."
  default     = 8000
}

variable "db_name" {
  type        = string
  default     = "propel"
  description = "Initial database name."
}

variable "db_min_acu" {
  type        = number
  default     = 0.5
  description = "Aurora Serverless v2 min ACU."
}

variable "db_max_acu" {
  type        = number
  default     = 2
  description = "Aurora Serverless v2 max ACU."
}

variable "db_skip_final_snapshot" {
  type        = bool
  default     = true
  description = "Skip final snapshot on destroy."
}

variable "db_deletion_protection" {
  type        = bool
  default     = false
  description = "Enable RDS deletion protection."
}

variable "db_enable_data_api" {
  type        = bool
  default     = false
  description = "Enable the RDS Data API (HTTP endpoint) for debugging access."
}

variable "app_environment" {
  type        = map(string)
  default     = {}
  description = "Plain environment variables injected into the API container (forwarded from GitHub Actions variables)."
}

variable "app_secrets" {
  type        = map(string)
  default     = {}
  sensitive   = true
  description = "Sensitive key/value pairs stored in Secrets Manager and injected into the API container."
}

variable "api_image_tag" {
  type        = string
  default     = "latest"
  description = "ECR image tag the API service runs."
}

variable "api_desired_count" {
  type        = number
  default     = 1
  description = "Number of API tasks (fixed; no autoscaling)."
}

variable "ingestion_enabled" {
  type        = bool
  default     = false
  description = "Provision the long-running Dagster ingestion ECS service + UI."
}

variable "dagster_fqdn" {
  type        = string
  default     = ""
  description = "Dagster UI FQDN served via the ALB, e.g. dagster.beta.propel.ninja."
}

variable "dagster_allowed_cidrs" {
  type        = list(string)
  default     = []
  description = "Source IP CIDRs allowed to reach the Dagster UI. Empty = open (no auth)."
}

variable "dask_enabled" {
  type        = bool
  default     = true
  description = "Provision the scale-to-zero Dask worker fleet for distributed ingestion (requires ingestion_enabled)."
}

variable "dask_worker_max_count" {
  type        = number
  default     = 4
  description = "Ceiling for the Dagster-driven Dask worker autoscaler."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to all resources."
}
