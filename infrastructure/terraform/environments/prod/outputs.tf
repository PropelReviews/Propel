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

output "ecr_repository_url" {
  value = module.stack.ecr_repository_url
}

output "ecs_cluster_name" {
  value = module.stack.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.stack.ecs_service_name
}

output "ecs_ingestion_service_name" {
  value = module.stack.ecs_ingestion_service_name
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

output "beta_delegation_name_servers" {
  value       = data.aws_route53_zone.beta.name_servers
  description = "NS records delegated to the beta account for beta.propel.ninja."
}
