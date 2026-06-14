data "aws_route53_zone" "this" {
  name         = var.zone_name
  private_zone = false
}

locals {
  name_prefix  = "propel-${var.environment}"
  api_fqdn     = "${var.api_subdomain}.${var.zone_name}"
  app_fqdn     = "${var.app_subdomain}.${var.zone_name}"
  dagster_fqdn = "${var.dagster_subdomain}.${var.zone_name}"
  auth_fqdn    = "${var.auth_subdomain}.${var.zone_name}"
  # Landing site on the zone apex + www (e.g. beta.propel.ninja +
  # www.beta.propel.ninja). The apex (first entry) is the canonical URL.
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
  db_skip_final_snapshot = true
  db_deletion_protection = false
  # Data API on in beta only, for ad-hoc query debugging (already enabled
  # manually on the cluster; this keeps Terraform from turning it back off).
  db_enable_data_api = true

  api_image_tag     = var.api_image_tag
  api_desired_count = var.api_desired_count
  app_environment   = var.app_environment
  app_secrets       = var.app_secrets

  ingestion_enabled     = var.ingestion_enabled
  dagster_fqdn          = local.dagster_fqdn
  dagster_allowed_cidrs = var.dagster_allowed_cidrs

  # Beta does NOT host Zitadel; it consumes the single shared prod instance.
  # zitadel_enabled stays false so no auth.<beta-zone> ECS/ALB/DNS is created;
  # zitadel_issuer_url points cross-account at the prod instance.
  zitadel_enabled    = false
  zitadel_issuer_url = var.zitadel_issuer_url
  auth_fqdn          = local.auth_fqdn

  tags = local.tags
}
