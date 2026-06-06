# Remote state lives in the PROD account (616938645090). Bucket and lock table
# are created once during bootstrap (see infrastructure/terraform/README.md).
terraform {
  backend "s3" {
    bucket         = "propel-tfstate-prod-616938645090"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "propel-tf-locks"
    encrypt        = true
  }
}
