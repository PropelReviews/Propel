variable "name_prefix" {
  type        = string
  description = "Prefix for named resources, e.g. propel-beta."
}

variable "domain_name" {
  type        = string
  description = "Frontend FQDN served by CloudFront, e.g. app.beta.propel.ninja."
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM certificate ARN in us-east-1 covering the frontend FQDN."
}

variable "price_class" {
  type        = string
  description = "CloudFront price class."
  default     = "PriceClass_100"
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}
