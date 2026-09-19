"""The knowledge base: everything the assistant is allowed to know.

Kept in its own module so it can be edited (and diffed) without touching the handler,
and so the tests can import the handler with a stub knowledge base.
"""

KNOWLEDGE_BASE = """
# About Abheenash Rajolu

Application and systems support engineer working across AWS and on-premises Linux, based
in Houston, TX (open to relocation). Currently IT Analyst - Application Support at
Phillips 66 (Feb 2026 - present). Diagnoses and fixes defects in internally developed
Java, C++, Perl, and Ruby services used by roughly 13,000 people; traces data problems to
root cause with SQL against Oracle and SQL Server; and builds the alarms and logging that
surface failures before users report them. AWS Certified DevOps Engineer - Professional
(DOP-C02) and AWS Certified Solutions Architect - Associate (SAA-C03); also holds AWS
Certified Cloud Practitioner (CLF-C02). M.S. in Computer & Systems Engineering, University
of Houston (GPA 3.60, Dec 2025; coursework: Principles of Internetworking, Introduction to
Cybersecurity, Open Systems, Advanced Computer Architecture), with C++ concurrency and Java
diagnostics work alongside it. B.Tech in Computer Science and Engineering, VRS & YRN
College of Engineering and Technology, Chirala, India (Apr 2023).
Links: portfolio abheenash.com, GitHub github.com/Abheenash, LinkedIn
linkedin.com/in/abheenash, email abheenash007@gmail.com. Resume PDF:
abheenash.com/assets/Abheenash-Rajolu-Resume.pdf.

# Professional experience

IT Analyst - Application Support, Phillips 66, Houston, TX (Feb 2026 - present). Current
role. Supports 7 workplace applications used by approximately 13,000 employees and
contractors across refineries, terminals, and offices - contractor access, work permits,
and facility requests - running on AWS and on-premises RHEL. Works approximately 20
production tickets a month, diagnosing from Splunk logs and SQL against Oracle and SQL
Server. Fixed 12 production defects across Java, C++, Perl, and Ruby, including a C++
memory leak in the site-access service that had been managed with weekly restarts;
reproduced it, isolated it with Valgrind and GDB, and shipped a peer-reviewed patch. Built
monitoring that shortened detection: Splunk alerts and dashboards for the on-premises Perl
and C++ estate, Terraform-managed CloudWatch alarms for AWS workloads, and structured error
logging; caught 3 failures before any user reported them. Partners with developers on
enhancements, including bulk work-permit renewals in a legacy Ruby on Rails application.
On-call one week in five: runs recovery procedures, coordinates outages across
development, plant IT, and the service desk, maintains runbooks, and presents incident
trends at monthly service reviews. Uses GitHub Copilot and Amazon Q for log triage and
script drafting, reviewing every generated suggestion before it ships.
Project - Contractor Access Sync Repair: built a nightly Java reconciliation job covering
approximately 3,500 active contractor records across Oracle, ISNetworld, and SAP, with
automated repair, SQL diagnostics, and ServiceNow escalation on RHEL cron and Control-M;
it retired a manual pre-shift check and took team-wide gate-access tickets from
approximately 12 a month to 4.

Systems Engineering Intern, Cloudflare, Austin, TX (May 2025 - Aug 2025). Built a Go
service auditing on-call ownership and alert routing across approximately 120 internal
services, exporting gaps as Prometheus metrics; surfaced 31 services with missing or stale
owners and delivered a runbook and Grafana dashboard. Investigated service-catalog
discrepancies with read-only SQL against PostgreSQL and ClickHouse, found approximately
1,800 orphaned ownership records, and wrote a cleanup procedure with a tested rollback.
Shadowed the on-call rotation for 6 weeks, triaged Prometheus and Grafana alerts alongside
a mentor and coauthored 2 incident reports; raised test coverage on an internal Go service
above 70%, added CI checks, and containerized 2 Python tools for Kubernetes.

DevOps Engineer - AWS Cloud Operations, HCLTech, Hyderabad, India (Apr 2022 - Dec 2023).
Supported a U.S. client's B2B platform on AWS serving approximately 300 business customers
and 3 million API requests daily; troubleshot compute, load balancing, database, IAM, VPC,
and OS issues across ECS Fargate, RDS, and Linux. On-call one week in four: triaged
CloudWatch and PagerDuty alerts, assessed customer impact, executed documented rollbacks
and recovery procedures, and authored more than 10 root-cause analyses. Replaced
static-threshold alarms with golden-signal and composite service-health alarms tied to
runbooks, cutting pages per on-call week from approximately 30 to 11. Automated recurring
support work with Python, Boto3, Lambda, EventBridge, and Systems Manager - patch-compliance
reporting, non-production scheduling, resource health checks - saving approximately 4 hours
weekly; remediated more than 60 AWS Config, GuardDuty, and Security Hub findings.
Project - Release Pipeline Automation: rebuilt a half-manual release process into an
automated GitHub Actions pipeline with tests, security scanning, image versioning, staged
deployments, a gated production rollout, and automatic rollback; release time fell from
approximately 2 hours to under 20 minutes and console-based production changes ended.
Project - Infrastructure-as-Code Migration: moved approximately 150 manually provisioned
AWS resources into reusable Terraform modules with remote state, locking, pull-request
plans, and drift detection; eliminated configuration drift and cut new-environment setup
from approximately 3 days to 90 minutes.

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

# September 2026 upgrades to the cloud projects (all pushed, CI green on every repo)

- Production Triage Toolkit: run-to-run comparison shipped (--compare, --history-dir,
  --fail-on-regression) classifying checks as NEW/RESOLVED/WORSENED/IMPROVED/UNCHANGED/BROKE/
  RECOVERED; 172 tests (128 unit, 44 integration); docs-freshness gate re-verified.
- Cloud Observability & Incident Response: multi-window multi-burn-rate SLO alarms, anomaly-
  detection alarms (p95 latency, traffic drop), an AWS Fault Injection Service GameDay
  experiment whose stop condition is the composite health alarm, and an automated drill
  script; measured detection 105 s (restore -> OK 297 s) on 2026-09-19.
- AWS Cloud Operations & Recovery Lab: both drill findings fixed (alarm on HealthyHostCount
  below desired; RDS connection threshold derived from the instance class ceiling), the
  non-prod scheduler as Terraform (EventBridge Scheduler, scoped IAM, errors alarm), 12 moto
  tests, CI with a runbook link check.
- Secure Container Pipeline: a 4th gate (pytest against mocked DynamoDB), CycloneDX SBOM,
  image secret scan, non-root assertion, a gated CD job with keyless cosign signing, Dependabot;
  app got /ready (DynamoDB reachable) vs /health, validation, pagination, security headers;
  ECS deployment circuit breaker with rollback, CPU autoscaling, optional TLS 1.3 + redirect.
- Serverless File Share: header-injection fix (filename sanitisation + RFC 5987
  Content-Disposition), structured JSON logs, reaper partial-batch failure reporting, 16 moto
  tests, checkov baseline (encrypted DLQ, multipart-abort lifecycle) — deployed live and
  smoke-tested.
- AWS EKS Platform: both drill findings fixed — preStop drain + readiness 503 on SIGTERM +
  15 s deregistration delay (the 502s), /burn in a child process with separate
  liveness/readiness/startup probes (the restart under load); PodDisruptionBudget; CI with
  kubeconform and a manifest policy check; runtime image without pip/setuptools (Trivy clean).
- Job Hunt Command Center: repair of Bedrock replies truncated at max_tokens (bracket repair
  keeps completed values, invents nothing), 8 tests; CI runs all 12 Lambdas' suites (114 tests).
- Portfolio AI Assistant (this chatbot): EMF metrics per request (latency, tokens, cache reads,
  cost — $0.0015 per answer, 4,000 cache-read tokens), origin allow-list in the Lambda, history
  repair, X-Ray, 3 alarms + dashboard, 24 tests with a fake Bedrock, and a 12-case
  prompt-injection eval run against the live endpoint: 12/12.

# Systems / C++ projects (the foundation under the cloud work) — all rebuilt Sep 2026 with
# tests that run under ThreadSanitizer/AddressSanitizer in CI on Linux and macOS

- Parallel Thread Pool (C++17, header-only): work-stealing scheduler (per-worker deques, pop own
  front, steal a random victim's back), submit() returning std::future with exception
  propagation, post(), parallel_for whose calling thread helps run tasks so nested loops can't
  deadlock, wait_idle, backpressure, graceful shutdown. Submitters only take the wake-up mutex
  when a sleeper count says a worker is parked; workers spin briefly before parking. 16 tests.
  Apple M4 results: 64 compute-bound tasks 5.37x on 10 cores; 1M tiny tasks 0.60 -> 1.98 M/s
  after the spin-before-park change; fork-join spawn tree 4.24 M tasks/s stealing vs 3.38 M
  single-queue; on heavy-tailed pre-submitted tasks stealing and a global FIFO queue tie (5.8x) —
  reported honestly. github.com/Abheenash/parallel-thread-pool
- Parallel Heat Diffusion (C++17): 2-D heat-equation stencil with four backends — serial,
  spawn-per-step std::thread, persistent std::thread workers with a spinning sense-reversal
  barrier, and OpenMP — on one flat contiguous grid. 320 backend/thread-count combinations are
  bitwise-identical to serial (memcmp), plus physical invariants including exact mirror symmetry
  (which required grouping the commutative neighbour pairs). A STREAM-style --bandwidth probe
  quantifies the roofline: the 2000x2000 grid reaches ~100 GB/s at 4 threads against a measured
  98 GB/s copy ceiling, so the ~1.9-2.0x observed is the maximum possible; a cache-resident
  512x512 grid shows spawn-per-step slower than serial (0.81x), condvar barrier 2.14x, spin
  barrier 2.89x. github.com/Abheenash/parallel-heat-diffusion
- Concurrent Key-Value Store (C++17, raw POSIX sockets): Redis-style server. 64-way sharded
  store under std::shared_mutex with lazy + swept TTL expiry; newline-framed protocol with 22
  commands (GET SET SETNX DEL EXISTS INCR DECR INCRBY EXPIRE PEXPIRE TTL PTTL PERSIST MGET KEYS
  DBSIZE PING ECHO INFO FLUSHALL COMPACT QUIT); append-only-file persistence with replay,
  absolute-deadline TTLs, atomic-rename compaction and fsync always/everysec/no; two I/O
  models — thread-per-connection and N poll() reactors that each accept from the shared
  listener; sigwait shutdown; a load generator reporting p50/p90/p99/p99.9; Dockerfile.
  Apple M4, loopback, 50 clients pipeline 32: 5.09 M req/s with 64 shards vs 1.23 M with a
  global mutex (p99 1.1 ms vs 9 ms); ~200 K req/s unpipelined (kernel round trip dominates);
  500 clients accepted 502/502 with zero errors; AOF everysec costs ~11%, always 2.5x. Five
  real bugs found and fixed by its own tests (POLLHUP with buffered data on macOS, close() not
  waking accept(), SIGINT ignored by background jobs, accepted sockets inheriting O_NONBLOCK on
  BSD, listen backlog overflow with a single acceptor). github.com/Abheenash/concurrent-kv-store

# Skills

Languages: Python (Boto3), Java, C++, C, SQL, Bash, Perl, Ruby, Go, JavaScript.
Operations & Linux: Linux/Unix (RHEL), systemd, cron, incident response, root-cause
analysis, runbooks, log analysis, query plans (EXPLAIN), GDB, Valgrind, strace, ServiceNow,
Control-M.
Monitoring: CloudWatch (alarms, dashboards, Synthetics), Logs Insights, X-Ray, RUM,
CloudTrail, Splunk, PagerDuty, Prometheus, Grafana, SLOs and error budgets, failure drills,
restore testing.
Cloud infrastructure, automation & CI/CD: EC2, ECS Fargate, EKS, Lambda, API Gateway, S3,
ALB, VPC, IAM, KMS, Secrets Manager, WAF, EventBridge, SQS, Systems Manager, RDS, Terraform,
GitHub Actions (OIDC), Docker, Kubernetes. Also used in projects: DynamoDB, Cognito, SES,
SNS, CloudFront, Route 53, Step Functions, GuardDuty, Config, Security Hub, Bedrock.
DevSecOps: IAM least privilege, KMS/SSE encryption, Checkov, tfsec, Trivy, gitleaks.
Databases: Oracle, SQL Server, PostgreSQL, MySQL, DynamoDB, ClickHouse.
Systems & software engineering: TCP/IP, DNS, load balancing, auto scaling, Multi-AZ
failover, distributed systems, operating systems, object-oriented design, data structures,
algorithms, complexity analysis, multithreading, work stealing, lock sharding, POSIX sockets,
poll() event loops, OpenMP, ThreadSanitizer/AddressSanitizer, CMake, roofline analysis.
Generative AI: Amazon Bedrock (Claude), GitHub Copilot, Amazon Q, prompt engineering,
context-grounded prompting, prompt-injection defense, output evaluation.

# This chatbot itself

This assistant is itself an AWS project: API Gateway -> Lambda -> Amazon Bedrock (Claude Haiku
4.5), with the knowledge base delivered as a cached system prompt (no vector database needed,
since the corpus is small). It's Abheenash's GenAI project. Repo:
github.com/Abheenash/portfolio-ai-assistant
"""
