SHELL := /bin/bash
TF    := terraform -chdir=terraform
REGION ?= us-east-1
TAG    ?= latest
IMAGE  := gatekeeper

.PHONY: help install test lint run tf-init tf-validate ecr build push deploy url destroy

help:
	@echo "Local:"
	@echo "  make install     install dev dependencies"
	@echo "  make test        run pytest (mock mode)"
	@echo "  make lint        run ruff"
	@echo "  make run         run the API locally (uvicorn)"
	@echo "Deploy (needs AWS creds + Docker running):"
	@echo "  make deploy      ECR -> build/push image -> apply Lambda + API Gateway"
	@echo "  make url         print the deployed API URL"
	@echo "  make destroy     tear everything down"

# ---- Local dev ----
install:
	pip install -r requirements-dev.txt

test:
	pytest -q

lint:
	ruff check .

run:
	uvicorn app.main:app --reload

# ---- Infra / deploy ----
tf-init:
	$(TF) init -backend-config=backend.hcl

tf-validate: tf-init
	$(TF) validate

# 1) Create only the ECR repo so we have somewhere to push.
ecr: tf-init
	$(TF) apply -target=aws_ecr_repository.this -auto-approve

# 2) Build the Lambda container image (single-arch linux/amd64 for Lambda).
build:
	docker build --provenance=false --platform linux/amd64 -t $(IMAGE):$(TAG) .

# 3) Log in to ECR and push.
push: ecr build
	$(eval REPO := $(shell $(TF) output -raw ecr_repository_url))
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(REPO)
	docker tag $(IMAGE):$(TAG) $(REPO):$(TAG)
	docker push $(REPO):$(TAG)

# 4) Apply the rest (Lambda + API Gateway) now that the image exists.
deploy: push
	$(TF) apply -auto-approve
	@echo "API URL: $$($(TF) output -raw api_url)"

url:
	@$(TF) output -raw api_url

destroy:
	$(TF) destroy -auto-approve
