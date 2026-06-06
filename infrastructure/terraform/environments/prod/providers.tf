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
