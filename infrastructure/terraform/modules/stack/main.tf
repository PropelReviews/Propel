terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

# Full per-environment stack: VPC + Aurora Serverless v2 + ECS/ALB API +
# S3/CloudFront frontend + ACM cert + Route53 alias records. Shared by the
# beta and prod environment roots so they stay (almost) identical.

locals {
  landing_dns_fqdns = coalesce(var.landing_dns_fqdns, var.landing_fqdns)

  # Route53 record names are relative to the hosted zone apex (e.g. "www" in
  # beta.propel.ninja, not "www.beta.propel.ninja"). Using FQDNs in delegated
  # child zones can leave www.* resolving to NS/SOA only instead of the alias.
  landing_route53_names = {
    for fqdn in local.landing_dns_fqdns :
    fqdn => fqdn == var.zone_name ? "" : replace(fqdn, ".${var.zone_name}", "")
  }

  # Browser calls from the deployed SPA (app.<zone>) are cross-origin relative to
  # api.<zone>. Starlette returns 400 on OPTIONS preflight when the Origin is not
  # listed here, so always inject the app origin. The landing site (apex/www)
  # also calls the API (waitlist signup), so its origins are injected too. Extra
  # origins can still be supplied via GitHub Actions variables
  # (app_environment.CORS_ALLOWED_ORIGINS).
  cors_allowed_origins = join(",", distinct(concat(
    ["https://${var.app_fqdn}"],
    [for fqdn in var.landing_fqdns : "https://${fqdn}"],
    [
      for origin in split(",", lookup(var.app_environment, "CORS_ALLOWED_ORIGINS", "")) :
      trimspace(origin) if trimspace(origin) != ""
    ],
    ["http://localhost:5173", "http://localhost:3000"],
  )))

  api_app_environment = merge(var.app_environment, {
    CORS_ALLOWED_ORIGINS = local.cors_allowed_origins
  })
}

module "network" {
  source         = "../network"
  name_prefix    = var.name_prefix
  container_port = var.container_port
  tags           = var.tags
}

module "database" {
  source                = "../database"
  name_prefix           = var.name_prefix
  subnet_ids            = module.network.private_subnet_ids
  rds_security_group_id = module.network.rds_security_group_id
  db_name               = var.db_name
  min_acu               = var.db_min_acu
  max_acu               = var.db_max_acu
  skip_final_snapshot   = var.db_skip_final_snapshot
  deletion_protection   = var.db_deletion_protection
  enable_data_api       = var.db_enable_data_api
  tags                  = var.tags
}

module "dns" {
  source        = "../dns"
  zone_id       = var.zone_id
  api_fqdn      = var.api_fqdn
  app_fqdn      = var.app_fqdn
  dagster_fqdn  = var.ingestion_enabled ? var.dagster_fqdn : ""
  landing_fqdns = var.landing_fqdns
  tags          = var.tags
}

module "api" {
  source                  = "../api"
  name_prefix             = var.name_prefix
  vpc_id                  = module.network.vpc_id
  public_subnet_ids       = module.network.public_subnet_ids
  private_subnet_ids      = module.network.private_subnet_ids
  alb_security_group_id   = module.network.alb_security_group_id
  ecs_security_group_id   = module.network.ecs_security_group_id
  acm_certificate_arn     = module.dns.certificate_arn
  database_url_secret_arn = module.database.database_url_secret_arn
  app_environment         = local.api_app_environment
  app_secrets             = var.app_secrets
  container_port          = var.container_port
  image_tag               = var.api_image_tag
  desired_count           = var.api_desired_count

  ingestion_enabled     = var.ingestion_enabled
  dagster_fqdn          = var.dagster_fqdn
  dagster_allowed_cidrs = var.dagster_allowed_cidrs

  tags = var.tags
}

module "frontend" {
  source              = "../frontend"
  name_prefix         = var.name_prefix
  domain_name         = var.app_fqdn
  acm_certificate_arn = module.dns.certificate_arn
  tags                = var.tags
}

# Marketing landing site served on the apex + www domains (separate S3 +
# CloudFront from the app frontend so the two deploy independently).
module "landing" {
  source              = "../landing"
  name_prefix         = var.name_prefix
  domain_names        = var.landing_fqdns
  acm_certificate_arn = module.dns.certificate_arn
  tags                = var.tags
}

# api.<zone> -> ALB
resource "aws_route53_record" "api" {
  zone_id = var.zone_id
  name    = var.api_fqdn
  type    = "A"

  alias {
    name                   = module.api.alb_dns_name
    zone_id                = module.api.alb_zone_id
    evaluate_target_health = true
  }
}

# dagster.<zone> -> ALB (host-based routing to the Dagster webserver target group)
resource "aws_route53_record" "dagster" {
  count   = var.ingestion_enabled ? 1 : 0
  zone_id = var.zone_id
  name    = var.dagster_fqdn
  type    = "A"

  alias {
    name                   = module.api.alb_dns_name
    zone_id                = module.api.alb_zone_id
    evaluate_target_health = true
  }
}

# app.<zone> -> CloudFront
resource "aws_route53_record" "app" {
  zone_id = var.zone_id
  name    = var.app_fqdn
  type    = "A"

  alias {
    name                   = module.frontend.distribution_domain_name
    zone_id                = module.frontend.distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

# Landing FQDNs (apex + www) -> landing CloudFront. One alias per name.
resource "aws_route53_record" "landing" {
  for_each = local.landing_route53_names

  zone_id = var.zone_id
  name    = each.value
  type    = "A"

  alias {
    name                   = module.landing.distribution_domain_name
    zone_id                = module.landing.distribution_hosted_zone_id
    evaluate_target_health = false
  }

  allow_overwrite = true
}
