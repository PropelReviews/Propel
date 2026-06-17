variable "name_prefix" {
  type        = string
  description = "Prefix for named resources, e.g. propel-beta."
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for the DB subnet group."
}

variable "rds_security_group_id" {
  type        = string
  description = "Security group allowing Postgres access from the ECS tasks."
}

variable "db_name" {
  type        = string
  description = "Initial database name."
  default     = "propel"
}

variable "master_username" {
  type        = string
  description = "Aurora master username."
  default     = "propel"
}

variable "engine_version" {
  type        = string
  description = "Aurora PostgreSQL engine version (must support Serverless v2)."
  default     = "18.3"
}

variable "min_acu" {
  type        = number
  description = "Serverless v2 minimum Aurora Capacity Units."
  default     = 0.5
}

variable "max_acu" {
  type        = number
  description = "Serverless v2 maximum Aurora Capacity Units."
  default     = 2
}

variable "skip_final_snapshot" {
  type        = bool
  description = "Skip the final snapshot on destroy (true for beta, false for prod)."
  default     = true
}

variable "deletion_protection" {
  type        = bool
  description = "Enable deletion protection on the cluster."
  default     = false
}

variable "enable_data_api" {
  type        = bool
  description = "Enable the RDS Data API (HTTP endpoint) for query access without a VPC connection (debugging)."
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}

variable "posthog_warehouse_enabled" {
  type        = bool
  description = "Enable Aurora logical replication, a public writer endpoint, and a PostHog CDC login secret."
  default     = true
}

variable "posthog_warehouse_username" {
  type        = string
  description = "Postgres role name for the PostHog data-warehouse connector."
  default     = "posthog"
}

variable "posthog_warehouse_publication" {
  type        = string
  description = "Logical-replication publication name (self-managed CDC mode in PostHog)."
  default     = "posthog"
}
