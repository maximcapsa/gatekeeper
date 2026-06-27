"""Tests for the SonarCloud client helpers (no network)."""

from __future__ import annotations

from app.sonar.client import _map_issue, wait_for_pr_analysis


def test_wait_for_pr_analysis_times_out_without_network():
    # timeout_s=0: the deadline is already past, so the loop body (and any HTTP
    # call) never runs — returns False immediately.
    assert wait_for_pr_analysis("proj", "1", timeout_s=0) is False


def test_map_issue_coerces_unknown_severity_and_type():
    issue = _map_issue(
        {"key": "k", "rule": "r", "severity": "WEIRD", "type": "ALIEN", "component": "c"}
    )
    assert issue.severity == "MAJOR"
    assert issue.type == "CODE_SMELL"
