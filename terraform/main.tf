terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    # Used by data.archive_file to zip the Lambda; was in use but unpinned.
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "portfolio-ai-assistant", ManagedBy = "terraform" }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}
variable "prefix" {
  type    = string
  default = "pai"
}
variable "model_id" {
  type    = string
  default = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}
variable "allowed_origins" {
  type        = list(string)
  description = "Browser origins the chat endpoint accepts (checked in the Lambda, not just CORS)."
  default     = ["https://abheenash.com", "https://www.abheenash.com"]
}
variable "alarm_email" {
  type        = string
  description = "Optional email for alarm notifications; empty = alarms with no action."
  default     = ""
}

data "aws_caller_identity" "current" {}

# --- package the Lambda -----------------------------------------------------
data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/lambda.zip"
}

# --- IAM: logs + invoke ONLY the Haiku model/profile ------------------------
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.prefix}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "xray" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

data "aws_iam_policy_document" "bedrock" {
  statement {
    sid     = "InvokeHaiku"
    actions = ["bedrock:InvokeModel"]
    # Cross-region inference profile routes to multiple US regions, so allow the
    # foundation model in any region plus this account's inference profile.
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.model_id}",
    ]
  }
}

resource "aws_iam_role_policy" "bedrock" {
  name   = "${var.prefix}-invoke-bedrock"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.bedrock.json
}

# --- Lambda -----------------------------------------------------------------
resource "aws_lambda_function" "chat" {
  function_name    = "${var.prefix}-chat"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.13"
  handler          = "app.handler"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 30
  memory_size      = 256
  # A function-level reserved-concurrency cap would be the natural cost guard here, but
  # this account sits at the AWS minimum quota (10 unreserved), which forbids reserving
  # any — so the account quota itself is the hard ceiling, and the hourly CostUsd alarm
  # below is the guard that actually fires. (checkov CKV_AWS_115 is accepted for that reason.)
  tracing_config {
    mode = "Active"
  }
  environment {
    variables = {
      MODEL_ID         = var.model_id
      MAX_TOKENS       = "512"
      MAX_INPUT_CHARS  = "1000"
      ALLOW_ORIGIN     = join(",", var.allowed_origins)
      METRIC_NAMESPACE = "PortfolioAssistant"
    }
  }
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.chat.function_name}"
  retention_in_days = 30
}

# --- HTTP API (throttled; Lambda owns CORS) ---------------------------------
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.prefix}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "chat" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.chat.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.chat.id}"
}

resource "aws_apigatewayv2_route" "options" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "OPTIONS /chat"
  target    = "integrations/${aws_apigatewayv2_integration.chat.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 5
    throttling_rate_limit  = 3
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGWInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chat.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

output "chat_endpoint" {
  value = "${aws_apigatewayv2_api.api.api_endpoint}/chat"
}

# --- Observability: alarms on the EMF metrics the Lambda emits + a dashboard --
resource "aws_sns_topic" "alerts" {
  count             = var.alarm_email == "" ? 0 : 1
  name              = "${var.prefix}-alerts"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alarm_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

locals {
  alarm_actions = var.alarm_email == "" ? [] : [aws_sns_topic.alerts[0].arn]
}

# Bedrock failures the retry loop could not absorb (5xx to the visitor).
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.prefix}-assistant-errors"
  namespace           = "PortfolioAssistant"
  metric_name         = "Errors"
  dimensions          = { Outcome = "error" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 3
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_description   = "3+ failed answers in 5 minutes"
  alarm_actions       = local.alarm_actions
}

# Slow answers: p95 end-to-end latency over 8 s means Bedrock is degraded or retrying.
resource "aws_cloudwatch_metric_alarm" "latency_p95" {
  alarm_name          = "${var.prefix}-assistant-latency-p95"
  namespace           = "PortfolioAssistant"
  metric_name         = "LatencyMs"
  dimensions          = { Outcome = "ok" }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 8000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}

# Cost guard: more than $0.50 of Bedrock spend in an hour is a scraper, not a visitor.
resource "aws_cloudwatch_metric_alarm" "spend" {
  alarm_name          = "${var.prefix}-assistant-hourly-spend"
  namespace           = "PortfolioAssistant"
  metric_name         = "CostUsd"
  dimensions          = { Outcome = "ok" }
  statistic           = "Sum"
  period              = 3600
  evaluation_periods  = 1
  threshold           = 0.5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}

resource "aws_cloudwatch_dashboard" "assistant" {
  dashboard_name = "${var.prefix}-assistant"
  dashboard_body = jsonencode({
    widgets = [
      { type = "metric", x = 0, y = 0, width = 8, height = 6, properties = {
        title = "Answers / rejections / errors", region = var.region, stat = "Sum", period = 300,
        metrics = [["PortfolioAssistant", "OutputTokens", "Outcome", "ok", { label = "answers (sample count)", stat = "SampleCount" }],
      [".", "Rejected", ".", "rejected"], [".", "Errors", ".", "error"]] } },
      { type = "metric", x = 8, y = 0, width = 8, height = 6, properties = {
        title = "Latency (ms)", region = var.region, period = 300,
      metrics = [["PortfolioAssistant", "LatencyMs", "Outcome", "ok", { stat = "p50" }], ["...", { stat = "p95" }], ["...", { stat = "Maximum" }]] } },
      { type = "metric", x = 16, y = 0, width = 8, height = 6, properties = {
        title = "Prompt cache: read vs fresh input tokens", region = var.region, stat = "Sum", period = 300,
      metrics = [["PortfolioAssistant", "CacheReadTokens", "Outcome", "ok"], [".", "InputTokens", ".", "."], [".", "CacheWriteTokens", ".", "."]] } },
      { type = "metric", x = 0, y = 6, width = 8, height = 6, properties = {
        title = "Cost (USD)", region = var.region, stat = "Sum", period = 3600,
      metrics = [["PortfolioAssistant", "CostUsd", "Outcome", "ok"]] } },
      { type = "metric", x = 8, y = 6, width = 8, height = 6, properties = {
        title = "Retries per answer", region = var.region, stat = "Average", period = 300,
      metrics = [["PortfolioAssistant", "Retries", "Outcome", "ok"]] } },
      { type = "metric", x = 16, y = 6, width = 8, height = 6, properties = {
        title = "API Gateway 4xx / 5xx / throttles", region = var.region, stat = "Sum", period = 300,
      metrics = [["AWS/ApiGateway", "4xx", "ApiId", aws_apigatewayv2_api.api.id], [".", "5xx", ".", "."]] } },
    ]
  })
}
