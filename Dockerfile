# AWS Lambda container image for the GateKeeper FastAPI service.
# Base image already contains the Lambda Runtime Interface Client.
FROM public.ecr.aws/lambda/python:3.12

# Install runtime dependencies (lean set — no uvicorn/pytest/ruff).
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Mangum handler: module path to the `handler` object.
CMD ["app.lambda_handler.handler"]
