output "certificate_arn" {
  value       = aws_acm_certificate_validation.this.certificate_arn
  description = "Validated ACM certificate ARN (us-east-1)."
}
