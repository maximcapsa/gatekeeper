variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name used for the ECR repo, Lambda function, and API."
  type        = string
  default     = "gatekeeper"
}

variable "image_tag" {
  description = "Container image tag deployed to Lambda."
  type        = string
  default     = "latest"
}

variable "groq_api_key" {
  description = "Groq API key for live LLM mode. Leave empty to run the API in mock mode."
  type        = string
  default     = ""
  sensitive   = true
}

variable "force_mock" {
  description = "Force deterministic mock mode in the deployed Lambda (no LLM calls)."
  type        = string
  default     = "true"
}

variable "lambda_memory_mb" {
  description = "Lambda memory size (MB)."
  type        = number
  default     = 512
}

variable "lambda_timeout_s" {
  description = "Lambda timeout (seconds)."
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}
