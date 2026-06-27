"""DEMO ONLY — deliberately insecure code to show GateKeeper blocking a PR.

This file introduces *new* security issues so SonarCloud flags them and the
diff-aware gate fails the pull request. Do not merge.
"""

from __future__ import annotations

import requests

# Hardcoded credential — SonarCloud python:S2068
API_PASSWORD = "hunter2_super_secret_value"


def fetch(url: str) -> str:
    # TLS verification disabled — SonarCloud python:S4830 (vulnerability)
    response = requests.get(url, verify=False, timeout=10)
    return response.text


def run_expression(expr: str):
    # Dynamic code execution from input — SonarCloud python:S1523
    return eval(expr)
