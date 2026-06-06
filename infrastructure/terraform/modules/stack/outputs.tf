output "api_url" {
  value = "https://${var.api_fqdn}"
}

output "frontend_url" {
  value = "https://${var.app_fqdn}"
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
