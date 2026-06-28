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
from urllib.parse import urlsplit

import httpx

from app.models import SonarIssue, SonarReport

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "sonar_issues.json"
DEFAULT_HOST = "https://sonarcloud.io"


def _sonar_base(host: str) -> str:
    """Validate and normalize the Sonar host to a bare ``scheme://netloc``.

    The host is operator config (SonarCloud or a self-hosted SonarQube), but it
    can originate from a CLI flag — so we never trust an injected path/query.
    Rebuilding from the parsed scheme+host prevents request forgery (SSRF).
    """
    parts = urlsplit(host or "")
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"invalid Sonar host: {host!r}")
    return f"{parts.scheme}://{parts.netloc}"

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


# SonarCloud rates hotspots by review priority, not severity. Map to our scale
# so they rank and display sensibly alongside issues.
_HOTSPOT_SEVERITY = {"HIGH": "CRITICAL", "MEDIUM": "MAJOR", "LOW": "MINOR"}


def fetch_report(
    project_key: str,
    pull_request: str | None = None,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    page_size: int = 500,
    include_hotspots: bool = False,
) -> SonarReport:
    """Fetch open issues for a project (optionally scoped to a pull request).

    Security Hotspots live behind a separate API; pass ``include_hotspots`` to
    fold the unreviewed ones in as SECURITY_HOTSPOT findings.
    """
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

    base = _sonar_base(host)
    issues: list[SonarIssue] = []
    with httpx.Client(timeout=30) as client:
        page = 1
        while True:
            params["p"] = page
            resp = client.get(f"{base}/api/issues/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            issues.extend(_map_issue(i) for i in data.get("issues", []))
            total = data.get("paging", {}).get("total", len(issues))
            if not data.get("issues") or page * page_size >= total:
                break
            page += 1

    if include_hotspots:
        issues.extend(fetch_hotspots(project_key, pull_request, host, token))

    return SonarReport(
        project=project_key,
        pull_request=str(pull_request) if pull_request else None,
        issues=issues,
    )


def fetch_hotspots(
    project_key: str,
    pull_request: str | None = None,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    page_size: int = 500,
) -> list[SonarIssue]:
    """Fetch unreviewed Security Hotspots as SECURITY_HOTSPOT findings."""
    token = token or os.getenv("SONAR_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    params: dict[str, str | int] = {
        "projectKey": project_key,
        "status": "TO_REVIEW",
        "ps": page_size,
    }
    if pull_request:
        params["pullRequest"] = str(pull_request)

    base = _sonar_base(host)
    out: list[SonarIssue] = []
    with httpx.Client(timeout=30) as client:
        page = 1
        while True:
            params["p"] = page
            resp = client.get(f"{base}/api/hotspots/search", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for h in data.get("hotspots", []):
                prob = h.get("vulnerabilityProbability", "MEDIUM")
                out.append(
                    SonarIssue(
                        key=h.get("key", ""),
                        rule=h.get("ruleKey", ""),
                        severity=_HOTSPOT_SEVERITY.get(prob, "MAJOR"),
                        type="SECURITY_HOTSPOT",
                        component=h.get("component", ""),
                        line=h.get("line"),
                        message=h.get("message", ""),
                        status=h.get("status", "TO_REVIEW"),
                    )
                )
            total = data.get("paging", {}).get("total", len(out))
            if not data.get("hotspots") or page * page_size >= total:
                break
            page += 1
    return out


def _sha_match(analyzed: str, head: str) -> bool:
    """Tolerant SHA comparison (either may be an abbreviation of the other)."""
    if not analyzed or not head:
        return False
    n = min(len(analyzed), len(head))
    return analyzed[:n].lower() == head[:n].lower()


def pr_analysis_ready(
    project_key: str,
    pull_request: str,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    head_sha: str | None = None,
) -> bool:
    """True once SonarCloud has analyzed this pull request.

    When ``head_sha`` is given, require the analyzed commit to match it — so a
    push to an existing PR isn't gated against the *previous* commit's stale
    analysis (the PR is already in the list from before).
    """
    token = token or os.getenv("SONAR_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    base = _sonar_base(host)
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{base}/api/project_pull_requests/list",
            params={"project": project_key},
            headers=headers,
        )
        if resp.status_code != 200:
            return False
        for pr in resp.json().get("pullRequests", []):
            if str(pr.get("key")) != str(pull_request) or not pr.get("analysisDate"):
                continue
            if head_sha:
                return _sha_match((pr.get("commit") or {}).get("sha", ""), head_sha)
            return True
    return False


def wait_for_pr_analysis(
    project_key: str,
    pull_request: str,
    host: str = DEFAULT_HOST,
    token: str | None = None,
    timeout_s: float = 150,
    interval_s: float = 8,
    head_sha: str | None = None,
) -> bool:
    """Poll until the PR's analysis is ready (for ``head_sha`` if given).

    Avoids the race where the gate fetches findings before SonarCloud has
    analyzed the current commit. Best-effort: returns False on timeout so the
    caller can proceed anyway.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if pr_analysis_ready(project_key, pull_request, host, token, head_sha):
            return True
        time.sleep(interval_s)
    return False
