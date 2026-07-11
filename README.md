# Portfolio AI Assistant

> A serverless GenAI chatbot that answers recruiter/visitor questions about me,
> grounded **only** in a curated knowledge base. Live on [abheenash.com](https://abheenash.com).

**API Gateway (HTTP) → Lambda (Python) → Amazon Bedrock (Claude Haiku 4.5)**

## Why this project exists

My other four AWS projects show **build → ship → operate → recover**. This one adds the
piece recruiters keep asking about: *can you actually wire an LLM into a product safely?*
It's small on purpose — the interesting parts are the engineering decisions, not the size.

## Design decisions

| Decision | Why |
| --- | --- |
| **Context-stuffing, not vector RAG** | The corpus (my experience, projects, skills) is a few KB. A vector DB would be cost + latency + ops for nothing. The whole KB rides in the system prompt. |
| **Bedrock prompt caching** (`cache_control: ephemeral`) | The KB prefix is identical on every call, so it's cached — repeat calls pay a fraction of the input cost and are faster. Bedrock needs *manual* cache breakpoints (automatic caching isn't supported), so the breakpoint is explicit. |
| **Cross-region inference profile** (`us.anthropic.claude-haiku-4-5-…`) | Bedrock requires the inference-profile ID, not the bare `anthropic.…` model ID, for on-demand Claude 4.x. |
| **Grounded system guard** | The model is instructed to answer *only* from the KB and to refuse off-topic / prompt-injection attempts ("write me code", "ignore your instructions"). No hallucinated employers or numbers. |
| **Guardrails in the Lambda, not just the prompt** | 1 KB input cap, 512-token output cap, history trimmed to the last 6 turns, and API Gateway stage throttling (3 rps / burst 5) so a scraper can't run up a Bedrock bill. |
| **Least-privilege IAM** | The Lambda role can call `bedrock:InvokeModel` on the *one* Haiku model/profile and nothing else. |

## Architecture

```
Browser widget (abheenash.com)
        │  POST /chat  {message, history[]}
        ▼
API Gateway (HTTP API, throttled)
        ▼
Lambda  app.handler  (Python 3.12)
   • validates + caps input
   • builds Messages body w/ cached system prompt
        ▼
Amazon Bedrock  InvokeModel
   Claude Haiku 4.5  (us.anthropic.claude-haiku-4-5-20251001-v1:0)
        ▲
        └── reply {reply}  →  rendered in the chat widget
```

## Repo map

| Path | What |
| --- | --- |
| `lambda/app.py` | The handler: validation, guardrails, Bedrock call, CORS |
| `terraform/main.tf` | IAM (least-privilege), Lambda, HTTP API, throttling, log group |
| `web/` | The drop-in chat widget (HTML/CSS/JS) embedded in the portfolio |

## Deploy

```bash
cd terraform
terraform init
terraform apply
# -> outputs chat_endpoint, e.g. https://abc123.execute-api.us-east-1.amazonaws.com/chat
```

Then point the widget's `ENDPOINT` at that URL.

## Cost

Effectively $0 idle (Lambda + HTTP API + Bedrock are all pay-per-use). At Haiku 4.5
pricing ($1 / $5 per 1M tokens) with prompt caching on the ~1–2K-token KB prefix, a
typical Q&A costs a fraction of a cent. Throttling caps the worst case.

---

*Part of a cloud portfolio — build → ship → operate → recover → **and now, GenAI**. More at [abheenash.com](https://abheenash.com).*
