data "aws_route53_zone" "this" {
  name         = var.zone_name
  private_zone = false
}

locals {
  name_prefix  = "propel-${var.environment}"
  api_fqdn     = "${var.api_subdomain}.${var.zone_name}"
  app_fqdn     = "${var.app_subdomain}.${var.zone_name}"
  dagster_fqdn = "${var.dagster_subdomain}.${var.zone_name}"
  # Landing site on the zone apex + www (e.g. propel.ninja +
  # www.propel.ninja). The apex (first entry) is the canonical URL.
  landing_fqdns = [var.zone_name, "www.${var.zone_name}"]

  tags = {
    Project     = "propel"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "stack" {
  source = "../../modules/stack"

  name_prefix   = local.name_prefix
  zone_id       = data.aws_route53_zone.this.zone_id
  zone_name     = var.zone_name
  api_fqdn      = local.api_fqdn
  app_fqdn      = local.app_fqdn
  landing_fqdns = local.landing_fqdns

  db_min_acu             = var.db_min_acu
  db_max_acu             = var.db_max_acu
  db_engine_version      = var.db_engine_version
  db_skip_final_snapshot = false
  db_deletion_protection = true

  api_image_tag     = var.api_image_tag
  api_desired_count = var.api_desired_count
  app_environment   = var.app_environment
  app_secrets       = var.app_secrets

  ingestion_enabled     = var.ingestion_enabled
  dagster_fqdn          = local.dagster_fqdn
  dagster_allowed_cidrs = var.dagster_allowed_cidrs

  tags = local.tags
}
