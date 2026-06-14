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

variable "dagster_fqdn" {
  type        = string
  description = "Dagster UI FQDN added as a certificate SAN, e.g. dagster.beta.propel.ninja. Empty to omit."
  default     = ""
}

variable "auth_fqdn" {
  type        = string
  description = "Zitadel FQDN added as a certificate SAN, e.g. auth.beta.propel.ninja. Empty to omit."
  default     = ""
}

variable "landing_fqdns" {
  type        = list(string)
  description = "Landing site FQDNs (apex + www) added as certificate SANs, e.g. [\"propel.ninja\", \"www.propel.ninja\"]."
  default     = []
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to all resources."
  default     = {}
}
