"""Tests for per-repo gate policy (.gatekeeper.yml)."""

from __future__ import annotations

import pytest

from app.agents.graph import run_review
from app.config import get_settings
from app.models import SonarIssue, SonarReport
from app.policy import DEFAULT_POLICY, GatePolicy, load_policy, parse_policy


@pytest.fixture(autouse=True)
def force_mock():
    settings = get_settings()
    original = settings.force_mock
    settings.force_mock = True
    yield
    settings.force_mock = original


def _issue(key, severity, type_, component="proj:app/x.py", line=1):
    return SonarIssue(
        key=key, rule="r", severity=severity, type=type_,
        component=component, line=line, message="m",
    )


def _report(*issues):
    return SonarReport(project="proj", issues=list(issues))


# --- parsing -------------------------------------------------------------

def test_parse_uppercases_and_filters_severities():
    p = parse_policy("blocking_severities: [major, nonsense, critical]")
    assert p.blocking_severities == ("MAJOR", "CRITICAL")


def test_parse_accepts_scalar_lists_and_flags():
    p = parse_policy(
        "fail_on_vulnerability: false\n"
        "fail_on_security_hotspot: true\n"
        "enforce: false\n"
        "ignore_paths: tests/**\n"
    )
    assert p.fail_on_vulnerability is False
    assert p.fail_on_security_hotspot is True
    assert p.enforce is False
    assert p.ignore_paths == ("tests/**",)


def test_load_policy_falls_back_on_missing_or_malformed():
    assert load_policy(None) == DEFAULT_POLICY
    assert load_policy("") == DEFAULT_POLICY
    assert load_policy("just a string") == DEFAULT_POLICY  # not a mapping
    assert load_policy(": : bad yaml :") == DEFAULT_POLICY


def test_unknown_keys_are_ignored():
    p = parse_policy("blocking_severities: [BLOCKER]\nfuture_option: 42\n")
    assert p.blocking_severities == ("BLOCKER",)


# --- behavior in the gate ------------------------------------------------

def test_ignore_paths_excludes_issue_entirely():
    report = _report(_issue("1", "BLOCKER", "BUG", component="proj:tests/test_x.py"))
    policy = GatePolicy(ignore_paths=("tests/**",))
    result = run_review(report, policy)
    assert result.gate == "PASS"
    assert result.triaged == []  # filtered before triage, not just at the gate


def test_custom_blocking_severity_fails_a_major():
    report = _report(_issue("1", "MAJOR", "CODE_SMELL"))
    # default policy would PASS a MAJOR code smell; this policy blocks it
    assert run_review(report, DEFAULT_POLICY).gate == "PASS"
    assert run_review(report, GatePolicy(blocking_severities=("MAJOR",))).gate == "FAIL"


def test_fail_on_vulnerability_toggle():
    report = _report(_issue("1", "MINOR", "VULNERABILITY"))
    assert run_review(report, DEFAULT_POLICY).gate == "FAIL"
    assert run_review(report, GatePolicy(fail_on_vulnerability=False)).gate == "PASS"


def test_fail_on_security_hotspot_toggle():
    report = _report(_issue("1", "MINOR", "SECURITY_HOTSPOT"))
    assert run_review(report, DEFAULT_POLICY).gate == "PASS"
    assert run_review(report, GatePolicy(fail_on_security_hotspot=True)).gate == "FAIL"
