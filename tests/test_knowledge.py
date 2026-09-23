"""The knowledge base is the only source of truth; keep it internally consistent."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from knowledge import KNOWLEDGE_BASE


def test_current_role_and_every_employer_present():
    for s in ("Phillips 66", "Cloudflare", "HCLTech", "IT Analyst"):
        assert s in KNOWLEDGE_BASE


def test_every_project_has_a_repo_link():
    for repo in ("production-triage-toolkit", "serverless-file-share", "secure-container-pipeline",
                 "cloud-observability-sre", "aws-cloudops-lab", "aws-eks-platform",
                 "job-hunt-command-center", "parallel-thread-pool", "parallel-heat-diffusion",
                 "concurrent-kv-store", "portfolio-ai-assistant", "aws-landing-zone"):
        assert f"github.com/Abheenash/{repo}" in KNOWLEDGE_BASE, repo


def test_contact_details_present():
    for s in ("abheenash007@gmail.com", "linkedin.com/in/abheenash", "abheenash.com"):
        assert s in KNOWLEDGE_BASE


def test_no_retired_name_form():
    assert "Rajolu Abheenash" not in KNOWLEDGE_BASE


def test_fits_comfortably_in_the_cached_prompt():
    # ~4 chars/token: keep the static prefix well under the model's context.
    assert len(KNOWLEDGE_BASE) < 40_000
