# Native terraform tests (`terraform test`) against a mocked provider — no AWS
# account, no Bedrock calls, no cost.
#
# The origin allow-list is the one that matters. This endpoint spends money per
# request against Bedrock, so an open origin is not just a CORS smell, it is
# somebody else's chatbot running on my bill.

mock_provider "aws" {
  override_data {
    target = data.aws_iam_policy_document.assume
    values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  override_data {
    target = data.aws_iam_policy_document.bedrock
    values = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
}
mock_provider "archive" {}

run "origin_allow_list_is_not_a_wildcard" {
  command = plan

  assert {
    condition = alltrue([
      for o in var.allowed_origins : o != "*" && startswith(o, "https://")
    ])
    error_message = "Every allowed origin must be an explicit https:// origin. A wildcard here means anyone can run this chatbot against my Bedrock bill."
  }

  assert {
    condition     = length(var.allowed_origins) > 0
    error_message = "An empty allow-list would be checked against nothing; be explicit."
  }
}

run "bedrock_permission_is_scoped_to_a_model" {
  command = plan

  # The IAM document itself is mocked, so what is assertable here is the input it
  # is built from: a model id must be set, and it must be an Anthropic model this
  # project actually uses — not a wildcard that would let the function invoke
  # anything in Bedrock.
  assert {
    condition     = can(regex("^[a-z0-9.:-]+$", var.model_id)) && !strcontains(var.model_id, "*")
    error_message = "model_id must name a specific model. A wildcard would widen bedrock:InvokeModel to every foundation model in the account."
  }
}

run "logs_do_not_retain_forever" {
  command = plan

  # Never-expiring log groups are the most common quiet AWS bill in a portfolio
  # account, and this one logs a prompt and a completion per request.
  assert {
    condition     = aws_cloudwatch_log_group.lambda.retention_in_days > 0 && aws_cloudwatch_log_group.lambda.retention_in_days <= 90
    error_message = "The chat log group must have a bounded retention. Default (never expire) accumulates prompt/completion logs forever."
  }
}
