output "ecr_repository_url" {
  description = "Push the container image here."
  value       = aws_ecr_repository.this.repository_url
}

output "api_url" {
  description = "Public base URL of the deployed API."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "lambda_function_name" {
  value = aws_lambda_function.this.function_name
}

output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN secret in the GitHub repo."
  value       = aws_iam_role.github_actions.arn
}
