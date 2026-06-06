variable "name_prefix" {
  type        = string
  description = "Prefix for named resources, e.g. propel-beta."
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.0.0.0/16"
}

variable "azs" {
  type        = list(string)
  description = "Availability zones to spread subnets across."
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for the public (ALB) subnets."
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for the private (ECS/RDS) subnets."
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "container_port" {
  type        = number
  description = "Container port the ALB forwards to (FastAPI)."
  default     = 8000
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}

# PostHog data-warehouse Postgres connector egress IPs (US + EU). Propel uses the
# US PostHog project; EU CIDRs are included so the allowlist matches PostHog docs.
variable "posthog_warehouse_cidrs" {
  type        = list(string)
  description = "PostHog warehouse connector source IPs (/32) allowed to reach Aurora on 5432."
  default = [
    "44.205.89.55/32",
    "44.208.188.173/32",
    "52.4.194.122/32",
    "3.75.65.221/32",
    "18.197.246.42/32",
    "3.120.223.253/32",
  ]
}
