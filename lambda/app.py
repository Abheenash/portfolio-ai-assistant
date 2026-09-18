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
# About Abheenash Rajolu

IT Analyst - Application Support at Phillips 66 in Houston, TX (Feb 2026 - present), and
AWS Certified DevOps Engineer - Professional. Experience in cloud operations, production
support, incident response, root-cause analysis, and CI/CD on AWS and Linux. Open to
cloud engineering, DevOps, SRE, production support, and cloud security roles; willing to
relocate. Certifications: AWS Certified DevOps Engineer - Professional (DOP-C02, Sep 2026),
AWS Certified Solutions Architect - Associate (SAA-C03, Jul 2026), AWS Certified Cloud
Practitioner (CLF-C02, Jun 2026). M.S. in Computer & Systems Engineering, University of
Houston (GPA 3.60, Dec 2025; coursework: Principles of Internetworking, Introduction to
Cybersecurity, Open Systems, Advanced Computer Architecture). B.Tech in CSE, VRS & YRN
College, Chirala, India (Apr 2023).
Links: portfolio abheenash.com, GitHub github.com/Abheenash, LinkedIn
linkedin.com/in/abheenash, email abheenash007@gmail.com.

# Professional experience

IT Analyst - Application Support, Phillips 66, Houston, TX (Feb 2026 - present). Current
role. Supports 7 workplace applications for ~13,000 employees and contractors across
refineries, terminals, and offices (contractor access, work permits, facility requests) on
AWS and on-premises RHEL. Resolves ~20 production tickets a month using Splunk and SQL
against Oracle and SQL Server. Fixed 12 production defects in Java, C++, and Perl,
including a C++ memory leak in the site-access service that had required weekly restarts:
reproduced it, isolated it with Valgrind and GDB, and delivered a peer-reviewed patch.
Partners with application developers on enhancements, including bulk work-permit renewals
in a legacy Ruby on Rails application. Added Splunk alerts and dashboards for on-prem
Perl/C++ applications, Terraform-managed CloudWatch alarms for AWS workloads, and
structured error logging; detected 3 failures before users reported them. On-call one week
in five: executes recovery procedures, coordinates outages with development, plant IT, and
the service desk, maintains runbooks, and presents trends at monthly service reviews. Uses
GitHub Copilot and Amazon Q for log triage and script drafting, reviewing every suggestion.
Project - Contractor Access Sync Repair (Apr 2026): built a nightly Java reconciliation job
for ~3,500 active contractor records across Oracle, ISNetworld, and SAP; automated repairs
and escalated unresolved issues with SQL diagnostics (RHEL/cron, Control-M, ServiceNow).
Replaced manual pre-shift checks, cutting team-wide gate-access tickets from ~12 to ~4 a
month, including during refinery turnarounds.

Systems Engineering Intern, Cloudflare, Austin, TX (May 2025 - Aug 2025). Built a Go
service to audit on-call ownership and alert routing across ~120 internal services,
exporting gaps as Prometheus metrics; identified 31 services with missing or stale owners
and delivered a runbook and a Grafana dashboard. Investigated service-catalog discrepancies
with read-only SQL against PostgreSQL and ClickHouse, found ~1,800 orphaned ownership
records, and developed a cleanup procedure with a tested rollback. Shadowed the on-call
rotation for 6 weeks, triaged Prometheus/Grafana alerts with a mentor, and coauthored 2
incident reports. Added tests and CI checks to an internal Go service (coverage above 70%)
and containerized 2 Python tools for Kubernetes.

DevOps Engineer - AWS Cloud Operations, HCLTech, Hyderabad, India (Apr 2022 - Dec 2023).
Supported a US client's AWS B2B platform (~300 business customers, ~3 million API requests
a day) across dev, staging, and production (ECS Fargate services behind an ALB, with RDS
and Linux hosts), troubleshooting network, database, IAM, and OS issues. On-call one week
in four: triaged CloudWatch and PagerDuty alerts, executed documented rollbacks/recoveries,
and wrote 10+ root-cause analyses. Replaced static-threshold alarms with golden-signal and
composite service-health alarms mapped to runbooks, cutting pages per on-call week from
~30 to ~11. Automated patch-compliance reporting, non-production scheduling, and health
checks with Python/Boto3, Lambda, EventBridge, and Systems Manager (~4 hours a week
saved); remediated 60+ findings from AWS Config, GuardDuty, and Security Hub.
Project - Release Pipeline Automation: rebuilt a half-manual release into a gated GitHub
Actions pipeline (tests, security scans, image versioning, staged deploys, production
approval gate, automatic rollback), cutting releases from ~2 hours to under 20 minutes
and ending console-based production changes.
Project - Infrastructure-as-Code Migration: moved ~150 hand-built AWS resources into
Terraform modules with remote state, locking, and drift detection, cutting new-environment
setup from ~3 days to ~90 minutes.

# Production Triage Toolkit (Java, Sep 2026)

A Java 17 CLI with 15 read-only SQL diagnostics against PostgreSQL (data drift, stalled
jobs, database health), ranked by severity, each linked to a runbook (confirm, fix,
prevent, escalate). Scans 10 million rows in 1,069 ms (1,228 ms with PostgreSQL pinned to
one CPU). Using EXPLAIN (ANALYZE, BUFFERS) he found an index causing 910,750 index probes,
replaced an O(n^2) self-join with an O(n log n) window function (2,147 ms -> 526 ms, total
2,647 ms -> 1,069 ms) and dropped four unused indexes (410 MB). Production-safe by design:
write-keyword screening, server-verified read-only session, per-check query timeout.
163 JUnit tests (121 unit, 42 PostgreSQL integration), 6 failure scenarios, 5 GitHub
Actions CI gates including a documentation-freshness check. Ships with Docker, systemd
units, a Kubernetes CronJob, and ECS/EventBridge Terraform.
Repo: github.com/Abheenash/production-triage-toolkit (CASE_STUDY.md has the write-up).

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

5. AWS EKS Platform: production-shaped Kubernetes on Amazon EKS in Terraform (managed node
   group, IRSA/OIDC, AWS Load Balancer Controller, Metrics Server, HPA), keyless GitHub
   Actions deploys. Drills: a deleted pod self-healed in ~7 s; HPA scaled 2 -> 6 pods in
   ~60 s under CPU load. Repo: github.com/Abheenash/aws-eks-platform

6. Job Hunt Command Center: Cognito-authenticated serverless job tracker (API Gateway,
   Lambda, DynamoDB, versioned S3, EventBridge, SES, Terraform). Amazon Bedrock (Claude)
   reads recruiter email over read-only IMAP, classifies replies/interviews/rejections
   through Step Functions, and drafts tailored resumes; includes a visa-sponsorship checker
   and an Openings Radar. Repo: github.com/Abheenash/job-hunt-command-center

# Systems / C++ projects (the foundation under the cloud work)

- Parallel Thread Pool (C++): persistent workers, mutex-protected task queue, condition-
  variable signaling; benchmarked 5.2x speedup at 8 threads. github.com/Abheenash/parallel-thread-pool
- Parallel Heat Diffusion (C++): 2D finite-difference PDE parallelized with std::thread and
  OpenMP; ~2.3x speedup, characterized as memory-bound, verified race-free with a checksum.
  github.com/Abheenash/parallel-heat-diffusion
- Concurrent Key-Value Store (C++): multithreaded TCP store on raw POSIX sockets, thread-per-
  connection, mutex-protected shared map. github.com/Abheenash/concurrent-kv-store

# Skills

Languages: Python (Boto3), SQL, Java, Bash, C, C++, JavaScript, Go, Ruby, Perl.
Operations: Linux/Unix (RHEL), incident response, on-call, root-cause analysis, runbooks,
log analysis, query plans (EXPLAIN), ServiceNow, Control-M, GDB, Valgrind, strace.
Monitoring: CloudWatch (alarms, dashboards, Synthetics, Logs Insights, RUM), X-Ray,
PagerDuty, Splunk, Prometheus, Grafana, SLOs, failure drills, restore testing.
Cloud & DevOps (AWS): EC2, ECS Fargate, EKS, ALB, S3, VPC, IAM, KMS, Lambda, API Gateway,
DynamoDB, Cognito, EventBridge, Systems Manager, CloudFront, Route 53, Secrets Manager, WAF,
SES, SNS, GuardDuty, Config, Security Hub, Bedrock; Terraform, GitHub Actions (OIDC keyless
auth, branch protection), Docker, Kubernetes, CronJobs, systemd timers.
DevSecOps: IAM least privilege, KMS/SSE encryption, Checkov, tfsec, Trivy, gitleaks.
Databases: PostgreSQL (EXPLAIN ANALYZE, read-only sessions), RDS, MySQL, DynamoDB, Oracle,
SQL Server, ClickHouse.
Systems & software: TCP/IP, DNS, load balancing, auto scaling, caching, replication,
Multi-AZ failover, object-oriented design, data structures and algorithms, complexity
analysis, multithreading, POSIX sockets, OpenMP.
Generative AI: Amazon Bedrock (Claude), prompt engineering, context-grounded prompting,
prompt-injection defense, output evaluation; GitHub Copilot and Amazon Q as assistants.

# This chatbot itself

This assistant is itself an AWS project: API Gateway -> Lambda -> Amazon Bedrock (Claude Haiku
4.5), with the knowledge base delivered as a cached system prompt (no vector database needed,
since the corpus is small). It's Abheenash's GenAI project. Repo:
github.com/Abheenash/portfolio-ai-assistant
"""

SYSTEM_GUARD = (
    "You are the friendly AI assistant on Abheenash Rajolu's portfolio website "
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
