"""Tests for the SonarCloud client helpers (no network)."""

from __future__ import annotations

from app.sonar.client import _map_issue, _sha_match, wait_for_pr_analysis


def test_wait_for_pr_analysis_times_out_without_network():
    # timeout_s=0: the deadline is already past, so the loop body (and any HTTP
    # call) never runs — returns False immediately.
    assert wait_for_pr_analysis("proj", "1", timeout_s=0) is False


def test_sha_match_full_and_abbreviated():
    full = "f5b64cf1a89bceecb0ff16e16b0822c10fb1eeca"
    assert _sha_match(full, full)
    assert _sha_match(full, "f5b64cf")          # head abbreviated
    assert _sha_match("f5b64cf", full)          # analyzed abbreviated
    assert _sha_match(full.upper(), full)       # case-insensitive


def test_sha_match_mismatch_and_empty():
    assert not _sha_match("f5b64cf", "deadbeef")
    assert not _sha_match("", "f5b64cf")
    assert not _sha_match("f5b64cf", "")


def test_map_issue_coerces_unknown_severity_and_type():
    issue = _map_issue(
        {"key": "k", "rule": "r", "severity": "WEIRD", "type": "ALIEN", "component": "c"}
    )
    assert issue.severity == "MAJOR"
    assert issue.type == "CODE_SMELL"
