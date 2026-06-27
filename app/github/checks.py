"""Post a GitHub Check Run — a first-class PR status check (pass/fail + summary)."""

from __future__ import annotations

import httpx

from app.github.auth import GITHUB_API

_MAX_SUMMARY = 65535  # GitHub Check Run output.summary limit


def post_check_run(
    owner: str,
    repo: str,
    head_sha: str,
    token: str,
    *,
    conclusion: str,
    title: str,
    summary: str,
    name: str = "GateKeeper",
) -> dict:
    """Create a completed Check Run on the PR's head commit.

    conclusion: "success" | "failure" | "neutral".
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    body = {
        "name": name,
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {"title": title, "summary": summary[:_MAX_SUMMARY]},
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/check-runs", headers=headers, json=body
        )
        resp.raise_for_status()
        return resp.json()
