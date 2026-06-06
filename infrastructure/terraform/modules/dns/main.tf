terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# One ACM certificate (us-east-1) covering the API, frontend, and landing FQDNs.
# Because the whole stack is in us-east-1, the same cert serves the ALB (api),
# the app CloudFront distribution, and the landing CloudFront distribution
# (apex + www). DNS-validated against the environment's hosted zone.
resource "aws_acm_certificate" "this" {
  domain_name               = var.api_fqdn
  subject_alternative_names = concat([var.app_fqdn], var.landing_fqdns)
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_route53_record" "validation" {
  for_each = {
    for dvo in aws_acm_certificate.this.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = var.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "this" {
  certificate_arn         = aws_acm_certificate.this.arn
  validation_record_fqdns = [for r in aws_route53_record.validation : r.fqdn]
}
