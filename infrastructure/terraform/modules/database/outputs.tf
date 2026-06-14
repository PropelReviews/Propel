output "cluster_endpoint" {
  value = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  value = aws_rds_cluster.this.reader_endpoint
}

output "database_url_secret_arn" {
  value       = aws_secretsmanager_secret.database_url.arn
  description = "Secrets Manager ARN holding the full DATABASE_URL."
}

output "master_username" {
  value       = var.master_username
  description = "Aurora master username (has CREATEDB; used to bootstrap the zitadel database)."
}

output "master_password" {
  value       = random_password.master.result
  description = "Aurora master password."
  sensitive   = true
}
