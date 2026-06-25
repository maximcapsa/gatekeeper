"""End-to-end tests for the agent graph, run in deterministic mock mode."""

from __future__ import annotations

import pytest

from app.agents.graph import run_review
from app.config import get_settings
from app.models import SonarIssue, SonarReport
from app.sonar.client import load_sample


@pytest.fixture(autouse=True)
def force_mock():
    """Run every test offline, regardless of a local .env key."""
    settings = get_settings()
    original = settings.force_mock
    settings.force_mock = True
    yield
    settings.force_mock = original


def test_sample_report_fails_the_gate():
    result = run_review(load_sample())

    assert result.gate == "FAIL"
    # Sample has an open CRITICAL vulnerability and a BLOCKER bug.
    assert "vulnerability" in result.reason.lower() or "blocking" in result.reason.lower()


def test_resolved_issues_are_excluded_from_triage():
    result = run_review(load_sample())
    keys = {t.issue.key for t in result.triaged}
    # AYx1-007 is RESOLVED in the sample and must not appear.
    assert "AYx1-007" not in keys


def test_security_findings_isolated():
    result = run_review(load_sample())
    security_types = {"VULNERABILITY", "SECURITY_HOTSPOT"}
    assert all(t.issue.type in security_types for t in result.security_findings)
    assert any(t.issue.type == "VULNERABILITY" for t in result.security_findings)


def test_fix_suggestions_generated_for_blocking_issues():
    result = run_review(load_sample())
    assert result.fix_suggestions, "expected at least one fix suggestion for blocking issues"
    assert len(result.fix_suggestions) <= get_settings().max_fix_suggestions


def test_summary_markdown_is_rendered():
    result = run_review(load_sample())
    assert result.project in result.summary_markdown
    assert "GateKeeper" in result.summary_markdown


def test_clean_report_passes_without_fixes():
    clean = SonarReport(
        project="clean-svc",
        issues=[
            SonarIssue(
                key="C-1",
                rule="python:S1135",
                severity="INFO",
                type="CODE_SMELL",
                component="app/x.py",
                line=3,
                message="Complete this TODO.",
            )
        ],
    )
    result = run_review(clean)
    assert result.gate == "PASS"
    assert result.fix_suggestions == []
