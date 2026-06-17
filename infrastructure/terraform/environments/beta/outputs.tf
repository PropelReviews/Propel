output "api_url" {
  value = module.stack.api_url
}

output "frontend_url" {
  value = module.stack.frontend_url
}

output "landing_url" {
  value = module.stack.landing_url
}

output "landing_bucket" {
  value = module.stack.landing_bucket
}

output "landing_cloudfront_distribution_id" {
  value = module.stack.landing_cloudfront_distribution_id
}

output "landing_cloudfront_domain_name" {
  value = module.stack.landing_cloudfront_domain_name
}

output "landing_cloudfront_hosted_zone_id" {
  value = module.stack.landing_cloudfront_hosted_zone_id
}

output "ecr_repository_url" {
  value = module.stack.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.stack.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.stack.ecs_service_name
}

output "ingestion_service_name" {
  value = module.stack.ingestion_service_name
}

output "dask_worker_service_name" {
  value = module.stack.dask_worker_service_name
}

output "dagster_url" {
  value = module.stack.dagster_url
}

output "frontend_bucket" {
  value = module.stack.frontend_bucket
}

output "cloudfront_distribution_id" {
  value = module.stack.cloudfront_distribution_id
}

output "alb_dns_name" {
  value = module.stack.alb_dns_name
}

output "posthog_warehouse_secret_name" {
  value       = module.stack.posthog_warehouse_secret_name
  description = "Secrets Manager secret with PostHog warehouse Postgres credentials."
}
