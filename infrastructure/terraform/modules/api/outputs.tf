output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "service_name" {
  value = aws_ecs_service.api.name
}

output "ingestion_service_name" {
  value = var.ingestion_enabled ? aws_ecs_service.ingestion[0].name : null
}

output "dask_worker_service_name" {
  value = local.dask_enabled ? aws_ecs_service.dask_workers[0].name : null
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "alb_zone_id" {
  value = aws_lb.this.zone_id
}

output "target_group_arn" {
  value = aws_lb_target_group.api.arn
}
