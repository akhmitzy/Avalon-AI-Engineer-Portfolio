variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod"
  }
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "Private subnets with a route to VPC endpoints (Bedrock, ECR, Logs, Secrets Manager) or a NAT gateway"
  type        = list(string)
}

variable "allowed_client_cidrs" {
  description = "CIDRs allowed to reach the internal ALB (n8n, worker, MCP hosts)"
  type        = list(string)
}

variable "api_image_tag" {
  type = string
}

variable "worker_image_tag" {
  type = string
}

variable "bedrock_model_ids" {
  description = "Foundation model ids the API may invoke"
  type        = list(string)
  default     = ["anthropic.claude-sonnet-5-5-v1:0", "amazon.titan-embed-text-v2:0"]
}

variable "bedrock_inference_profile_ids" {
  description = "Cross-region inference profile ids, if used (for example us.anthropic.claude-sonnet-5-5-v1:0)"
  type        = list(string)
  default     = []
}

variable "msk_cluster_arn" {
  description = "MSK cluster ARN for IAM auth. Leave empty to run without the worker."
  type        = string
  default     = ""
}

variable "kafka_brokers" {
  type    = string
  default = ""
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 2
}

variable "log_retention_days" {
  type    = number
  default = 365
}

variable "certificate_arn" {
  description = "ACM certificate for the internal ALB HTTPS listener"
  type        = string
}
