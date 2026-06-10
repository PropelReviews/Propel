output "api_url" {
  value = "https://${var.api_fqdn}"
}

output "frontend_url" {
  value = "https://${var.app_fqdn}"
}

output "landing_url" {
  value = "https://${var.landing_fqdns[0]}"
}

output "landing_bucket" {
  value = module.landing.bucket_name
}

output "landing_cloudfront_distribution_id" {
  value = module.landing.distribution_id
}

output "landing_cloudfront_domain_name" {
  value = module.landing.distribution_domain_name
}

output "landing_cloudfront_hosted_zone_id" {
  value = module.landing.distribution_hosted_zone_id
}

output "ecr_repository_url" {
  value = module.api.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.api.cluster_name
}

output "ecs_service_name" {
  value = module.api.service_name
}

output "ingestion_service_name" {
  value = module.api.ingestion_service_name
}

output "dask_worker_service_name" {
  value = module.api.dask_worker_service_name
}

output "dagster_url" {
  value = var.ingestion_enabled && var.dagster_fqdn != "" ? "https://${var.dagster_fqdn}" : null
}

output "alb_dns_name" {
  value = module.api.alb_dns_name
}

output "frontend_bucket" {
  value = module.frontend.bucket_name
}

output "cloudfront_distribution_id" {
  value = module.frontend.distribution_id
}

output "database_url_secret_arn" {
  value = module.database.database_url_secret_arn
}
