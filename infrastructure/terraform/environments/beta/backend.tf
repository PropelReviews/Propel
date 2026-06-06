# Remote state lives in the BETA account (536270449640). The bucket and lock
# table are created once during bootstrap (see infrastructure/terraform/README.md).
# Backend config cannot use variables, so these names are fixed by convention.
terraform {
  backend "s3" {
    bucket         = "propel-tfstate-beta-536270449640"
    key            = "beta/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "propel-tf-locks"
    encrypt        = true
  }
}
