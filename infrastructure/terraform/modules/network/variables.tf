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
