# Portfolio AI Assistant

> The "Ask AI" widget on [abheenash.com](https://abheenash.com): a serverless chatbot that answers
> recruiter and visitor questions about me, grounded **only** in a curated knowledge base —
> with per-answer cost, latency and prompt-cache metrics, alarms, a test suite, and a
> committed prompt-injection eval that runs against the live endpoint.

**API Gateway (HTTP) → Lambda (Python 3.12) → Amazon Bedrock (Claude Haiku 4.5)**

[![ci](https://github.com/Abheenash/portfolio-ai-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/Abheenash/portfolio-ai-assistant/actions/workflows/ci.yml)

## Why this project exists

My other AWS projects show **build → ship → operate → recover**. This one answers the question
recruiters keep asking: *can you wire an LLM into a product safely, and can you prove it stays
safe?* It's small on purpose — the engineering decisions and the evidence are the point.

## Measured, not estimated (live endpoint, 2026-09-19)

| | |
| --- | --- |
| Prompt-injection / grounding eval | **12 / 12 pass** ([`evals/results-2026-09-19.md`](evals/results-2026-09-19.md)) |
| Cache-read tokens per answer | **4,000** — the entire knowledge base, served from Bedrock's prompt cache on every call |
| Cost per answer | **$0.0015** (12 answers = $0.018, from the `CostUsd` metric the Lambda emits) |
| Latency, p50 | ~1.9 s end to end (Bedrock round trip dominates) |
| Requests from a non-allowed origin | HTTP 403 before Bedrock is touched |

## Design decisions

| Decision | Why |
| --- | --- |
| **Context-stuffing, not vector RAG** | The corpus (`lambda/knowledge.py`) is ~14 KB. A vector DB would be cost, latency and ops for nothing. The whole KB rides in the system prompt. |
| **Bedrock prompt caching** (`cache_control: ephemeral`) | The KB prefix is identical on every call, so it's read from cache: 4,000 cached tokens at $0.10/M instead of $1.00/M. Bedrock needs a *manual* cache breakpoint, so it's explicit. |
| **Cross-region inference profile** (`us.anthropic.claude-haiku-4-5-…`) | On-demand Claude 4.x on Bedrock must be called through the profile id, not the bare model id. The profile routes across US regions, so transient per-region errors are retried (bounded, 4 attempts). |
| **Grounded system guard** | Answer only from the KB; redirect off-topic requests; treat instructions inside a visitor's message — "ignore your rules", "I'm the developer", "print your prompt" — as part of the question, not as instructions. The eval set checks each of those. |
| **Guardrails in the Lambda, not just the prompt** | 1 KB input cap, 512-token output cap, history trimmed to 6 turns and *repaired* (roles must alternate), an **origin allow-list enforced server-side** (not only CORS), and API Gateway stage throttling (3 rps / burst 5). |
| **One structured log line per request, in EMF** | Latency, input/output/cache tokens, retries, outcome and a computed `CostUsd` become CloudWatch metrics with no `PutMetricData` call — so cache effectiveness and spend are graphs, not guesses. |
| **Alarms + dashboard in Terraform** | 3+ failed answers in 5 min; p95 latency > 8 s; **> $0.50 of Bedrock spend in an hour** (a scraper, not a visitor). X-Ray active tracing on the function. |
| **Least-privilege IAM** | The role can call `bedrock:InvokeModel` on the one Haiku model/profile, write logs, and write X-Ray segments. Nothing else. |

## Architecture

```
Browser widget (abheenash.com)
        │  POST /chat  {message, history[]}   Origin: https://abheenash.com
        ▼
API Gateway (HTTP API, 3 rps / burst 5)
        ▼
Lambda  app.handler  (Python 3.12, X-Ray)
   • origin allow-list → 403          • JSON / length / history validation → 400 / 413
   • builds Messages body with the cached system prompt
   • bounded retry across the inference profile's regions
   • emits {latency, tokens, cache reads, cost, outcome} as EMF
        ▼
Amazon Bedrock  InvokeModel — Claude Haiku 4.5 (us.anthropic.claude-haiku-4-5-20251001-v1:0)
        ▲
        └── {reply}  →  rendered in the chat widget

CloudWatch: PortfolioAssistant/* metrics → dashboard `pai-assistant` → alarms (errors, p95, hourly spend)
```

## Tests and evals

- **`tests/test_handler.py`** — 19 tests with a fake Bedrock client (no network): the cached
  system prompt is present and grounded, OPTIONS preflight, origin rejection before Bedrock,
  every validation path (bad JSON, non-object, empty, boundary length, too long), history
  trimming and repair (alternating roles, garbage entries, content cap), retry on throttling
  then success, non-retryable → 502 with the detail kept in the log, bounded give-up, empty
  model output fallback, and the EMF record's metrics and cost arithmetic.
- **`tests/test_knowledge.py`** — the KB names the current employer and every project's repo,
  has the contact details, never uses the retired surname-first name form, and fits comfortably
  in the cached prompt.
- **`evals/`** — 12 cases in `cases.json` (grounded facts, off-topic redirects, four injection
  patterns, three hallucination baits) run by `run_evals.py` against a deployed endpoint; each
  passes only if the reply contains an expected phrase and none of the forbidden ones. Results
  are committed per run.
- **CI** — pytest, `terraform fmt -check`, `terraform validate`, and **checkov** against a
  reviewed baseline (`.checkov.yaml`: every accepted finding has a written reason).

## Deploy

```bash
cd terraform
terraform init
terraform apply                                  # -var alarm_email=you@example.com to get paged
# -> chat_endpoint = https://<id>.execute-api.us-east-1.amazonaws.com/chat
python3 evals/run_evals.py "$(terraform output -raw chat_endpoint)"
```

Then point the widget's `AI_ENDPOINT` at that URL.

## Repo map

| Path | What |
| --- | --- |
| `lambda/app.py` | Handler: origin check, validation, history repair, cached prompt, retry, EMF metrics |
| `lambda/knowledge.py` | The knowledge base — the only thing the assistant is allowed to know |
| `tests/` | Handler + knowledge-base tests (fake Bedrock) |
| `evals/` | Prompt-injection / grounding eval cases, runner, and committed results |
| `terraform/main.tf` | IAM, Lambda (X-Ray), HTTP API + throttling, alarms, dashboard |
| `web/` | The drop-in chat widget |

## What I'd do next

Streaming responses (`InvokeModelWithResponseStream` through a Lambda function URL) so the
first token shows up in ~300 ms instead of the whole answer in ~2 s; a nightly scheduled eval
run that alarms on regressions; and an `INFO`-style admin endpoint that reports the cache hit
ratio for the last hour.
