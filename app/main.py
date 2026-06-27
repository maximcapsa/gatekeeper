"""FastAPI surface for GateKeeper.

Endpoints
    GET  /health         liveness + mode (mock vs live)
    POST /review         run the agent graph over a SonarReport payload
    POST /webhook/sonar  accept a SonarReport directly (CI / manual)
    POST /webhook/github GitHub App webhook: gate a PR and post a Check Run
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, Request, Response

from app import __version__
from app.agents.graph import run_review
from app.config import get_settings
from app.github.webhook import verify_signature
from app.models import ReviewResult, SonarReport

app = FastAPI(title="GateKeeper", version=__version__)

_PR_ACTIONS = {"opened", "synchronize", "reopened"}


@app.get("/health")
def health() -> dict:
    mode = "mock" if get_settings().use_mock else "live"
    return {"status": "ok", "version": __version__, "mode": mode}


@app.post("/review", response_model=ReviewResult)
def review(report: SonarReport) -> ReviewResult:
    return run_review(report)


@app.post("/webhook/sonar", response_model=ReviewResult)
def sonar_webhook(report: SonarReport) -> ReviewResult:
    return run_review(report)


@app.post("/webhook/github")
async def github_webhook(request: Request):
    """Verify the signature, then hand the PR off to the async worker.

    Returns 200 immediately (GitHub times out at ~10s); the gate itself runs in
    a separate Lambda invocation so it can wait for SonarCloud + call the LLM.
    """
    body = await request.body()
    if not verify_signature(body, request.headers.get("x-hub-signature-256")):
        return Response(status_code=401, content="invalid signature")

    if request.headers.get("x-github-event") != "pull_request":
        return {"status": "ignored"}

    payload = json.loads(body)
    if payload.get("action") not in _PR_ACTIONS:
        return {"status": "ignored", "action": payload.get("action")}

    pr = payload["pull_request"]
    job = {
        "owner": payload["repository"]["owner"]["login"],
        "repo": payload["repository"]["name"],
        "pr_number": payload["number"],
        "head_sha": pr["head"]["sha"],
        "installation_id": payload["installation"]["id"],
    }

    function_name = os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    if function_name:
        import boto3  # lazy: only needed in the Lambda webhook path

        boto3.client("lambda").invoke(
            FunctionName=function_name,
            InvocationType="Event",  # async — fire and forget
            Payload=json.dumps({"gatekeeper_job": job}).encode(),
        )
        return {"status": "accepted", "pr": job["pr_number"]}

    # Local / non-Lambda: process inline.
    from app.github.worker import run_job

    return run_job(job)
