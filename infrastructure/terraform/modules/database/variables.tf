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
  default     = "16.6"
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

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}
