"""FastAPI surface for GateKeeper.

Endpoints
    GET  /health         liveness + mode (mock vs live)
    POST /review         run the agent graph over a SonarReport payload
    POST /webhook/sonar  webhook entrypoint (CI posts the scan result here)
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.agents.graph import run_review
from app.config import get_settings
from app.models import ReviewResult, SonarReport

app = FastAPI(title="GateKeeper", version=__version__)


@app.get("/health")
def health() -> dict:
    mode = "mock" if get_settings().use_mock else "live"
    return {"status": "ok", "version": __version__, "mode": mode}


@app.post("/review", response_model=ReviewResult)
def review(report: SonarReport) -> ReviewResult:
    return run_review(report)


@app.post("/webhook/sonar", response_model=ReviewResult)
def sonar_webhook(report: SonarReport) -> ReviewResult:
    # Milestone 1: accept the report directly. A later milestone verifies the
    # SonarCloud webhook signature and posts the result back as a PR comment.
    return run_review(report)
