"""Load and parse SonarQube / SonarCloud findings.

Two sources:
  * ``load_sample`` — the bundled sample payload (offline demos, tests).
  * ``fetch_report`` — live findings from SonarCloud's /api/issues/search.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from app.models import SonarIssue, SonarReport

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "sonar_issues.json"
DEFAULT_HOST = "https://sonarcloud.io"

_VALID_SEVERITIES = {"BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"}
_VALID_TYPES = {"BUG", "VULNERABILITY", "CODE_SMELL", "SECURITY_HOTSPOT"}


def parse_report(data: dict) -> SonarReport:
    return SonarReport.model_validate(data)


def load_sample() -> SonarReport:
    return parse_report(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))


def _map_issue(raw: dict) -> SonarIssue:
    severity = raw.get("severity", "MAJOR")
    if severity not in _VALID_SEVERITIES:
        severity = "MAJOR"
    issue_type = raw.get("type", "CODE_SMELL")
    if issue_type not in _VALID_TYPES:
        issue_type = "CODE_SMELL"
    return SonarIssue(
        key=raw.get("key", ""),
        rule=raw.get("rule", ""),
        severity=severity,
        type=issue_type,
        component=raw.get("component", ""),
        line=raw.get("line"),
        message=raw.get("message", ""),
        status=raw.get("status", "OPEN"),
        effort=raw.get("effort"),
    )


def fetch_report(
    project_key: str,
    pull_request: str | None = None,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    page_size: int = 500,
) -> SonarReport:
    """Fetch open issues for a project (optionally scoped to a pull request)."""
    token = token or os.getenv("SONAR_TOKEN")
    if not project_key:
        raise ValueError("project_key is required to fetch from SonarCloud")

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params: dict[str, str | int] = {
        "componentKeys": project_key,
        "statuses": "OPEN,CONFIRMED,REOPENED",
        "ps": page_size,
    }
    if pull_request:
        params["pullRequest"] = str(pull_request)

    issues: list[SonarIssue] = []
    with httpx.Client(timeout=30) as client:
        page = 1
        while True:
            params["p"] = page
            resp = client.get(f"{host}/api/issues/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            issues.extend(_map_issue(i) for i in data.get("issues", []))
            total = data.get("paging", {}).get("total", len(issues))
            if not data.get("issues") or page * page_size >= total:
                break
            page += 1

    return SonarReport(
        project=project_key,
        pull_request=str(pull_request) if pull_request else None,
        issues=issues,
    )


def pr_analysis_ready(
    project_key: str,
    pull_request: str,
    host: str = DEFAULT_HOST,
    token: str | None = None,
) -> bool:
    """True once SonarCloud has analyzed this pull request at least once."""
    token = token or os.getenv("SONAR_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{host}/api/project_pull_requests/list",
            params={"project": project_key},
            headers=headers,
        )
        if resp.status_code != 200:
            return False
        for pr in resp.json().get("pullRequests", []):
            if str(pr.get("key")) == str(pull_request) and pr.get("analysisDate"):
                return True
    return False


def wait_for_pr_analysis(
    project_key: str,
    pull_request: str,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    timeout_s: float = 120,
    interval_s: float = 8,
) -> bool:
    """Poll until the PR has a SonarCloud analysis, or the timeout elapses.

    Avoids the race where the gate fetches findings before automatic analysis
    of the PR has landed. Best-effort: returns False on timeout so the caller
    can proceed anyway.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pr_analysis_ready(project_key, pull_request, host, token):
            return True
        time.sleep(interval_s)
    return False
