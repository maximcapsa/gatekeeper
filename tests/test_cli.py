"""Tests for the CLI entrypoint, run offline in mock mode against the sample."""

from __future__ import annotations

import pytest

from app import cli
from app.config import get_settings


@pytest.fixture(autouse=True)
def force_mock(monkeypatch):
    settings = get_settings()
    original = settings.force_mock
    settings.force_mock = True
    # Ensure 'auto' source resolves to the bundled sample, never the network.
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.delenv("GATEKEEPER_ENFORCE", raising=False)
    yield
    settings.force_mock = original


def test_cli_writes_report_and_fails_gate_when_enforcing(tmp_path):
    out = tmp_path / "report.md"
    code = cli.main(["--source", "sample", "--output", str(out)])
    # Sample has blocking findings; default enforcement -> non-zero exit.
    assert code == 1
    text = out.read_text(encoding="utf-8")
    assert "GateKeeper" in text
    assert "Demo data" in text  # sample-source banner


def test_cli_no_enforce_returns_zero(tmp_path):
    out = tmp_path / "report.md"
    code = cli.main(["--source", "sample", "--no-enforce", "--output", str(out)])
    assert code == 0


def test_cli_emits_github_outputs(tmp_path, monkeypatch):
    gh_output = tmp_path / "gh_output"
    gh_output.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_output))
    cli.main(["--source", "sample", "--no-enforce"])
    contents = gh_output.read_text(encoding="utf-8")
    assert "gate=FAIL" in contents
    assert "source=sample" in contents
