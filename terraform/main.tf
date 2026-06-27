data "aws_caller_identity" "current" {}

locals {
  image_uri = "${aws_ecr_repository.this.repository_url}:${var.image_tag}"
}

# ---------------------------------------------------------------------------
# ECR — holds the Lambda container image.
# Create this first (make ecr / -target), push the image, then apply the rest.
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "this" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep only the most recent images to stay within the ECR free tier (500 MB).
resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 3 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 3 }
      action       = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# IAM — Lambda execution role (logs only).
# ---------------------------------------------------------------------------
resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lets the webhook handler fire the gate asynchronously by invoking itself.
resource "aws_iam_role_policy" "lambda_self_invoke" {
  name = "${var.project_name}-self-invoke"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.this.arn
    }]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Lambda — the FastAPI app as a container image.
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "this" {
  function_name = var.project_name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.image_uri
  architectures = ["x86_64"]
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_s

  environment {
    variables = {
      GROQ_API_KEY               = var.groq_api_key
      FORCE_MOCK                 = var.force_mock
      SONAR_TOKEN                = var.sonar_token
      SONAR_HOST_URL             = "https://sonarcloud.io"
      GITHUB_APP_ID              = var.github_app_id
      GITHUB_APP_PRIVATE_KEY_B64 = var.github_app_private_key_b64
      GITHUB_WEBHOOK_SECRET      = var.github_webhook_secret
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_logs,
    aws_cloudwatch_log_group.lambda,
  ]

  # CI rolls the image via `aws lambda update-function-code`, so don't let
  # Terraform fight it on the next apply.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

# ---------------------------------------------------------------------------
# API Gateway (HTTP API v2) — public HTTPS endpoint -> Lambda.
# ---------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "this" {
  name          = var.project_name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "this" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.this.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}

resource "aws_apigatewayv2_route" "root" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /"
  target    = "integrations/${aws_apigatewayv2_integration.this.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.this.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}
