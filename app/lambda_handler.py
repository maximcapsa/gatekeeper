"""AWS Lambda entrypoint.

Mangum adapts the FastAPI ASGI app to the Lambda + API Gateway (HTTP API v2)
event/response format. The container's CMD points here: ``app.lambda_handler.handler``.
"""

from __future__ import annotations

from mangum import Mangum

from app.main import app

handler = Mangum(app)
