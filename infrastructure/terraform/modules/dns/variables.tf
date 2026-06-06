variable "zone_id" {
  type        = string
  description = "Route53 hosted zone ID the certificate is validated against."
}

variable "api_fqdn" {
  type        = string
  description = "API fully-qualified domain name, e.g. api.beta.propel.ninja."
}

variable "app_fqdn" {
  type        = string
  description = "Frontend fully-qualified domain name, e.g. app.beta.propel.ninja."
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}
