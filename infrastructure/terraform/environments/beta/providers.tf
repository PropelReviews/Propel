# Credentials are ambient: in CI, the GitHub Actions OIDC step assumes the
# PropelTerraform role in the beta account before Terraform runs; locally, use
# an AWS profile/SSO session for the beta account (see README). This avoids the
# OIDC "self-assume" footgun of putting assume_role on the primary provider.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "propel"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
