# GitHub Actions OIDC — lets the deploy workflow assume an AWS role for
# short-lived credentials, with no long-lived access keys stored in GitHub.

# The OIDC provider is account-wide (one per account). Reference the existing
# one rather than creating a duplicate (which AWS rejects).
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        # Trust only this repo, on the main branch or the production environment.
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_owner}/${var.github_repo}:ref:refs/heads/${var.github_branch}",
            "repo:${var.github_owner}/${var.github_repo}:environment:production"
          ]
        }
      }
    }]
  })
}

# Least-privilege: just enough to push an image and roll the Lambda.
resource "aws_iam_role_policy" "github_actions" {
  name = "${var.project_name}-github-actions-policy"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "ECRPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:DescribeImageScanFindings"
        ]
        Resource = aws_ecr_repository.this.arn
      },
      {
        Sid    = "LambdaDeploy"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration" # used by the `function-updated` waiter
        ]
        Resource = aws_lambda_function.this.arn
      }
    ]
  })
}
