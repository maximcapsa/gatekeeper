"""Load and parse SonarQube findings.

For milestone 1 this reads a static sample payload. A later milestone swaps
``load_sample`` for a real call to SonarCloud's /api/issues/search endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import SonarReport

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "samples" / "sonar_issues.json"


def parse_report(data: dict) -> SonarReport:
    return SonarReport.model_validate(data)


def load_sample() -> SonarReport:
    return parse_report(json.loads(SAMPLE_PATH.read_text(encoding="utf-8")))
