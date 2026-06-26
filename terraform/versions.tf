terraform {
  required_version = ">= 1.5"

  # Remote state in S3 (+ DynamoDB lock). Values are supplied at init via
  # `-backend-config=backend.hcl` so account-specific names aren't committed.
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}
