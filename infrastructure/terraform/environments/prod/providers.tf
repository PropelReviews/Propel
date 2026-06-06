# Default provider: prod account (616938645090). Credentials are ambient (CI
# OIDC assumes the prod PropelTerraform role; locally use a prod AWS profile).
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

# Cross-account, read-only provider into the beta account, used to look up the
# beta.propel.ninja hosted zone NS records so this config can write the
# delegation into the propel.ninja parent zone. The prod credentials must be
# allowed to assume this role (see README IAM section).
provider "aws" {
  alias  = "beta_dns"
  region = var.aws_region

  assume_role {
    role_arn = var.beta_dns_role_arn
  }
}
