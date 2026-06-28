"""Tests for the SonarCloud client helpers (no network)."""

from __future__ import annotations

import pytest

from app.sonar.client import _map_issue, _sha_match, _sonar_base, wait_for_pr_analysis


def test_sonar_base_normalizes_and_strips_path():
    assert _sonar_base("https://sonarcloud.io") == "https://sonarcloud.io"
    # An injected path/query is dropped — only scheme+host survive.
    assert _sonar_base("https://sonarcloud.io/evil?x=1") == "https://sonarcloud.io"
    assert _sonar_base("https://sonarqube.internal:9000/ctx") == "https://sonarqube.internal:9000"


def test_sonar_base_rejects_invalid_host():
    # Empty, no scheme, or no host all rejected (no insecure-protocol literals here).
    for bad in ["", "https://", "sonarcloud.io", "no-scheme"]:
        with pytest.raises(ValueError):
            _sonar_base(bad)


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
