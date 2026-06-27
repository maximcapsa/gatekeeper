"""AWS Lambda entrypoint.

Mangum adapts the FastAPI ASGI app to the Lambda + API Gateway (HTTP API v2)
event/response format. The container's CMD points here: ``app.lambda_handler.handler``.
"""

from __future__ import annotations

from mangum import Mangum

from app.main import app

_asgi_handler = Mangum(app)


def handler(event, context):
    """Route async self-invoke jobs to the worker; everything else to FastAPI.

    The webhook endpoint fires a `{"gatekeeper_job": ...}` async invocation;
    those events come straight to this handler (not through API Gateway).
    """
    if isinstance(event, dict) and "gatekeeper_job" in event:
        from app.github.worker import run_job

        return run_job(event["gatekeeper_job"])
    return _asgi_handler(event, context)
