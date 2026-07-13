terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Private bucket holding the built marketing site (dist-landing/). Never public;
# only CloudFront can read it via Origin Access Control. Mirrors the frontend
# module but serves the apex + www domains from a single distribution.
resource "aws_s3_bucket" "site" {
  bucket = "${var.name_prefix}-landing"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket                  = aws_s3_bucket.site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${var.name_prefix}-landing-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Redirects www.* hosts to their apex for a single canonical URL.
resource "aws_cloudfront_function" "redirect_www" {
  name    = "${var.name_prefix}-landing-redirect-www"
  runtime = "cloudfront-js-2.0"
  comment = "301 www.* to apex for the ${var.name_prefix} landing site."
  publish = true
  code    = file("${path.module}/redirect-www.js")
}

resource "aws_cloudfront_distribution" "site" {
  enabled = true
  # The landing build emits landing.html (Vite uses the entry file name), so it
  # is the root object and the SPA fallback target.
  default_root_object = "landing.html"
  aliases             = var.domain_names
  comment             = "${var.name_prefix} landing"
  price_class         = var.price_class

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.site.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
  }

  default_cache_behavior {
    target_origin_id       = "s3-${aws_s3_bucket.site.id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    # AWS managed "CachingOptimized" policy.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.redirect_www.arn
    }
  }

  # SPA routing: serve landing.html for client-side routes / missing keys.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/landing.html"
  }
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/landing.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.acm_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = var.tags
}

# Allow only this CloudFront distribution to read objects from the bucket.
data "aws_iam_policy_document" "site" {
  statement {
    sid       = "AllowCloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.site.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.site.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site.json
}

# Versioned landing archives under releases/<sha>/ for rollback.sh. Expire after
# 30 days so the bucket does not grow without bound (ECR keeps 30 SHA tags).
resource "aws_s3_bucket_lifecycle_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    id     = "expire-old-releases"
    status = "Enabled"

    filter {
      prefix = "releases/"
    }

    expiration {
      days = 30
    }
  }
}
