"""The async worker: gate a PR and post the result as a GitHub Check Run.

Runs out-of-band from the webhook (which must return 200 within ~10s) so it can
wait for SonarCloud's PR analysis and make LLM calls without timing out GitHub.
"""

from __future__ import annotations

from typing import TypedDict

from app.agents.graph import run_review
from app.github.auth import installation_token
from app.github.checks import post_check_run
from app.github.repo import get_file
from app.policy import POLICY_FILE, load_policy
from app.sonar.client import fetch_report, wait_for_pr_analysis


class GateJob(TypedDict):
    owner: str
    repo: str
    pr_number: int
    head_sha: str
    installation_id: int


def run_job(job: GateJob) -> dict:
    owner, repo = job["owner"], job["repo"]
    pr = str(job["pr_number"])
    # SonarCloud's default project key for a GitHub repo is "<owner>_<repo>".
    project_key = f"{owner}_{repo}"

    token = installation_token(job["installation_id"])

    # Per-repo policy lives in .gatekeeper.yml at the PR head; missing/bad -> defaults.
    policy_text = get_file(owner, repo, POLICY_FILE, job["head_sha"], token)
    policy = load_policy(policy_text)

    wait_for_pr_analysis(project_key, pr)
    report = fetch_report(project_key=project_key, pull_request=pr)
    result = run_review(report, policy)

    # Advisory mode (enforce: false): report a failing gate without blocking the merge.
    if result.gate == "PASS":
        conclusion = "success"
    elif policy.enforce:
        conclusion = "failure"
    else:
        conclusion = "neutral"

    post_check_run(
        owner,
        repo,
        job["head_sha"],
        token,
        conclusion=conclusion,
        title=f"GateKeeper — {result.gate}",
        summary=result.summary_markdown,
    )
    return {"gate": result.gate, "conclusion": conclusion, "pr": pr}
