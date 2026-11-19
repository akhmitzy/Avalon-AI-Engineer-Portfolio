terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  # backend "s3" {}  # configure per environment: bucket, key, region, dynamodb_table, encrypt = true
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "dxreview"
      Environment = var.environment
      DataClass   = "phi-adjacent"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  name       = "dxreview-${var.environment}"
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  # Least privilege: only the exact models the service calls.
  bedrock_model_arns = concat(
    [for m in var.bedrock_model_ids : "arn:${local.partition}:bedrock:${var.region}::foundation-model/${m}"],
    [for p in var.bedrock_inference_profile_ids : "arn:${local.partition}:bedrock:${var.region}:${local.account_id}:inference-profile/${p}"],
  )
}
