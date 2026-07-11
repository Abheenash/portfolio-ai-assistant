"""Portfolio AI assistant — API Gateway -> Lambda -> Amazon Bedrock (Claude Haiku 4.5).

Answers visitor questions about Abheenash, grounded ONLY in the knowledge base below.
No vector DB: the whole corpus is small, so it's stuffed into a cached system prompt
(Bedrock prompt caching makes the static prefix ~0.1x on repeat calls). See README.
"""
import json
import os
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get(
    "MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "512"))
MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "1000"))

_bedrock = boto3.client(
    "bedrock-runtime", region_name=REGION,
    config=Config(retries={"max_attempts": 2, "mode": "standard"}),
)

# --- knowledge base (everything the assistant is allowed to know) ------------
KNOWLEDGE_BASE = """
# About Rajolu Abheenash

Cloud & DevOps engineer based in Houston, TX. Open to work (cloud engineering,
DevOps, cloud security). AWS Certified Solutions Architect - Associate (SAA-C03)
and AWS Certified Cloud Practitioner (CLF-C02). M.S. in Computer & Systems
Engineering, University of Houston (GPA 3.60, Dec 2025). B.Tech in CSE, VRS & YRN
College, Chirala, India (Apr 2023).
Links: portfolio abheenash.com, GitHub github.com/Abheenash, LinkedIn
linkedin.com/in/abheenash, email abheenash007@gmail.com. Willing to relocate.

# Professional experience

DevOps Engineer - AWS Cloud Operations, HCLTech, Hyderabad, India (Apr 2022 - Dec 2023).
Supported a US client's containerized B2B platform across dev, staging, and production
AWS environments (ECS Fargate services behind an ALB, with RDS, Route 53, and Linux
hosts). Weekly on-call rotation triaging CloudWatch and PagerDuty alerts, executing
documented rollbacks/recoveries, and writing root-cause analyses. Migrated manual AWS
resources into reusable Terraform modules (remote state, locking, PR-gated plans, drift
detection). Rebuilt a manual release into a gated GitHub Actions pipeline with automatic
rollback. Tuned alerting toward golden-signal and composite service-health alarms mapped
to runbooks. Automated operations with Python/Boto3, Lambda, EventBridge, and Systems
Manager. Remediated findings from AWS Config, Inspector, GuardDuty, and Security Hub.

# Cloud projects (build -> ship -> operate -> recover)

1. Serverless File Share (build securely) - live at share.abheenash.com.
   Self-destructing encrypted file sharing on AWS: API Gateway -> Lambda -> S3/DynamoDB,
   customer-managed KMS encryption, one least-privilege IAM role per Lambda, TTL + DynamoDB
   Streams + a "reaper" Lambda that deletes files on expiry. Rebuilt as ~38 Terraform
   resources with keyless-OIDC GitHub Actions CI/CD. Two real bugs debugged and documented:
   SSE-KMS silently requiring AWS SigV4, and a DynamoDB Streams "LATEST" race.
   Repo: github.com/Abheenash/serverless-file-share

2. Secure Container Pipeline (ship securely).
   ECS Fargate service (private subnets, VPC endpoints instead of a NAT gateway, ALB + WAF,
   Secrets Manager, least-privilege task roles), all Terraform. DevSecOps GitHub Actions
   pipeline with three fail-the-build gates: gitleaks (secrets), Checkov/tfsec (IaC), Trivy
   (image + dependency CVEs). Proven by a pull request with a planted AWS credential being
   automatically blocked. Repo: github.com/Abheenash/secure-container-pipeline

3. Cloud Observability & Incident Response (operate reliably).
   Golden-signals CloudWatch dashboard, X-Ray tracing, SLOs with an error budget, alarms to
   SNS, and a Synthetics canary on the live serverless-file-share service - all Terraform.
   Validated with a failure-injection drill: throttled a Lambda to zero concurrency, the
   alarm auto-detected the outage in ~60 seconds, recovered via runbook.
   Repo: github.com/Abheenash/cloud-observability-sre

4. AWS Cloud Operations & Recovery Lab (recover under pressure).
   A day-2 ops lab: EC2 Auto Scaling Group + ALB + RDS Postgres in Terraform, golden-signals
   dashboard, alarms tied to runbooks, SSM patch management, backups. EC2 was chosen over
   Fargate on purpose so patching and instance-recovery drills are real. Executed live: five
   incident drills, a timed restore test, and a brownfield terraform-import/drift exercise.
   Measured results: three alarms fired with real detection times (5xx in 177s, latency in
   289s, DB-dependency in 166s); two drills exposed genuine alarm-tuning gaps (a single-
   instance failure self-heals faster than the alarm window; the RDS-connections threshold
   sat above the instance's real ceiling); and a database restore was measured at a 6m36s RTO
   against a 60-minute target, validated by querying the restored instance.
   Repo: github.com/Abheenash/aws-cloudops-lab

# Systems / C++ projects (the foundation under the cloud work)

- Parallel Thread Pool (C++): persistent workers, mutex-protected task queue, condition-
  variable signaling; benchmarked 5.2x speedup at 8 threads. github.com/Abheenash/parallel-thread-pool
- Parallel Heat Diffusion (C++): 2D finite-difference PDE parallelized with std::thread and
  OpenMP; ~2.3x speedup, characterized as memory-bound, verified race-free with a checksum.
  github.com/Abheenash/parallel-heat-diffusion
- Concurrent Key-Value Store (C++): multithreaded TCP store on raw POSIX sockets, thread-per-
  connection, mutex-protected shared map. github.com/Abheenash/concurrent-kv-store

# Skills

Cloud (AWS): Lambda, API Gateway, S3, DynamoDB, ECS Fargate, ECR, EC2 & Auto Scaling, RDS,
VPC, ALB, CloudFront, Route 53, KMS, Secrets Manager, IAM, WAF, CloudWatch, X-Ray, Synthetics,
SNS, EventBridge, Systems Manager, CloudTrail, GuardDuty, Config, Inspector, Security Hub,
Bedrock. IaC & CI/CD: Terraform, GitHub Actions, OIDC keyless auth, branch protection.
DevSecOps: IAM least privilege, KMS/SSE encryption, Checkov, tfsec, Trivy, gitleaks.
Observability/SRE: dashboards, alarms, Logs Insights, SLOs, incident response, runbooks, RCAs.
Programming: Python (Boto3), Bash, SQL, C, C++ (multithreading, OpenMP, POSIX sockets). Linux.

# This chatbot itself

This assistant is itself an AWS project: API Gateway -> Lambda -> Amazon Bedrock (Claude Haiku
4.5), with the knowledge base delivered as a cached system prompt (no vector database needed,
since the corpus is small). It's Abheenash's GenAI project. Repo:
github.com/Abheenash/portfolio-ai-assistant
"""

SYSTEM_GUARD = (
    "You are the friendly AI assistant on Rajolu Abheenash's portfolio website "
    "(abheenash.com). Answer visitor questions about Abheenash's experience, projects, "
    "skills, and background, using ONLY the knowledge base below. Be concise, warm, and "
    "specific; a few sentences is usually enough. If a question isn't covered by the "
    "knowledge base, say you can only answer questions about Abheenash and point them to "
    "his email (abheenash007@gmail.com) or LinkedIn. Never invent facts, numbers, "
    "employers, or projects that aren't in the knowledge base. If asked to do something "
    "unrelated (write code, tell jokes, general trivia), politely redirect to Abheenash.\n\n"
    "=== KNOWLEDGE BASE ===\n" + KNOWLEDGE_BASE
)

CORS = {
    "Access-Control-Allow-Origin": os.environ.get("ALLOW_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}


def _resp(status, body):
    return {"statusCode": status, "headers": {**CORS, "Content-Type": "application/json"},
            "body": json.dumps(body)}


def handler(event, context):
    method = (event.get("requestContext", {}).get("http", {}) or {}).get("method", "")
    if method == "OPTIONS":
        return _resp(200, {"ok": True})

    try:
        payload = json.loads(event.get("body") or "{}")
    except (ValueError, TypeError):
        return _resp(400, {"error": "invalid JSON"})

    message = (payload.get("message") or "").strip()
    if not message:
        return _resp(400, {"error": "message is required"})
    if len(message) > MAX_INPUT_CHARS:
        return _resp(413, {"error": "message too long"})

    # Optional short history: [{role: user|assistant, content: str}, ...]
    history = payload.get("history") or []
    messages = []
    for turn in history[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:MAX_INPUT_CHARS]})
    messages.append({"role": "user", "content": message})

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": SYSTEM_GUARD,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": messages,
    }

    payload_body = json.dumps(body)
    try:
        out = _invoke_with_retry(payload_body)
        data = json.loads(out["body"].read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return _resp(200, {"reply": text.strip() or "Sorry, I didn't catch that."})
    except Exception as e:  # noqa: BLE001 - surface a clean message, log the detail
        print(f"bedrock error: {type(e).__name__}: {e}")
        return _resp(502, {"error": "assistant temporarily unavailable"})


# Bedrock's cross-region inference profile re-routes each call across US regions.
# A few of those routes can transiently throttle or lag on subscription/agreement
# propagation, so retry a bounded number of times — the next attempt usually lands
# on a healthy region. Non-transient errors are re-raised immediately.
_RETRYABLE = {
    "ThrottlingException", "ModelNotReadyException", "ServiceUnavailableException",
    "InternalServerException", "ResourceNotFoundException", "AccessDeniedException",
}


def _invoke_with_retry(payload_body, attempts=4):
    last = None
    for i in range(attempts):
        try:
            return _bedrock.invoke_model(modelId=MODEL_ID, body=payload_body)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            last = e
            if code not in _RETRYABLE or i == attempts - 1:
                raise
            print(f"retryable bedrock error ({code}), attempt {i + 1}/{attempts}")
            time.sleep(0.4 * (i + 1))
    raise last
