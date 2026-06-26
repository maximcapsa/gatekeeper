# GateKeeper — AI code-quality gate for pull requests

[![CI](https://github.com/maximcapsa/gatekeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/maximcapsa/gatekeeper/actions/workflows/ci.yml)
[![GateKeeper](https://github.com/maximcapsa/gatekeeper/actions/workflows/gatekeeper.yml/badge.svg)](https://github.com/maximcapsa/gatekeeper/actions/workflows/gatekeeper.yml)

GateKeeper turns raw **SonarQube / SonarCloud** static-analysis findings into an
actionable PR review and a merge **pass/fail gate**. A **LangGraph** multi-agent
system — triage, security, fix-suggestion, and summarizer agents — runs behind a
**FastAPI** service and is wired into CI so every pull request gets reviewed
automatically.

Built as a DevOps portfolio project: CI/CD, a real quality gate, containerization,
Infrastructure-as-Code, and practical multi-agent AI — designed to run on the
**AWS Free Tier** with a **free Groq** LLM backend.

> **Status:** Milestones 1 & 4 complete — the multi-agent graph runs end-to-end, and
> a GitHub Actions pipeline runs the gate on every pull request, posts a review
> comment, and can block the merge. AWS deployment and live SonarCloud wiring land in
> the remaining milestones (see [Roadmap](#roadmap)).

---

## Architecture

```
PR opened ─▶ CI (GitHub Actions) ─▶ SonarCloud scan ─▶ webhook ─▶ FastAPI (AWS Lambda)
                                                                      │
                                                        LangGraph orchestrator
                                                        ┌──────┬─────────┬───────────┐
                                                     triage  security  fix_suggest  summarizer
                                                        └──────┴─────────┴───────────┘
                                                                      │
                                            PR review comment + pass/fail merge gate
```

**The graph:** `START → triage → security → (fix_suggest?) → summarizer → END`.
The fix-suggestion node is skipped via a conditional edge when there are no
blocking issues, so the stronger model is only used when it's needed.

| Agent | Job | Model |
|---|---|---|
| **triage** | Rank + dedupe findings (deterministic), add a one-line rationale each | `llama-3.1-8b-instant` |
| **security** | Isolate vulnerabilities & security hotspots | deterministic |
| **fix_suggest** | Draft a patch for the top blocking issues | `llama-3.3-70b-versatile` |
| **summarizer** | Decide the gate + render the Markdown PR comment | `llama-3.1-8b-instant` |

The **gate decision is a pure function** of the findings (never model-dependent),
so it's auditable and reproducible. The LLM adds explanation and fixes on top.

---

## Tech stack

| Area | Choice |
|---|---|
| API | FastAPI (served on AWS Lambda via Mangum in a later milestone) |
| Agent orchestration | LangGraph |
| LLM | Groq (free tier) — `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` |
| Static analysis | SonarCloud (free for public repos) |
| CI/CD | GitHub Actions (free for public repos) |
| Infra (planned) | AWS Lambda + API Gateway + DynamoDB + S3 + ECR, via Terraform |

---

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# Run the graph against the bundled sample payload
python scripts/run_local.py

# Run the API
uvicorn app.main:app --reload
# POST a SonarQube payload:
#   curl -X POST localhost:8000/review -H "content-type: application/json" \
#        --data @samples/sonar_issues.json

# Tests (run offline in mock mode)
pytest
```

### Mock vs live mode

Set `GROQ_API_KEY` in a `.env` file (see `.env.example`) for live LLM output.
**With no key, GateKeeper runs in deterministic mock mode** — the full graph still
executes, so you can develop and test the pipeline with zero cost or network.

---

## Cost & free-tier strategy

This project is deliberately engineered to cost ~nothing for a portfolio:

- **LLM** — Groq free tier; cheap/fast model for triage-style work, the stronger
  model only on blocking issues (conditional edge). Mock mode for CI/tests.
- **Static analysis** — SonarCloud is free for public repositories.
- **CI** — GitHub Actions is free for public repositories.
- **Compute (planned)** — AWS Lambda (1M free req/mo) + API Gateway free tier;
  DynamoDB (25 GB free), S3, and ECR (500 MB) all within free tier.
- **Bedrock note** — Amazon Bedrock would be the most "AWS-native" LLM path but is
  not free tier; Groq is used to keep the build free, with Bedrock documented as
  the enterprise swap-in.

---

## CI/CD

Two GitHub Actions workflows:

- **`ci.yml`** — runs `ruff` + `pytest` (mock mode) on every push and PR.
- **`gatekeeper.yml`** — on each PR: runs the gate, posts a sticky review comment
  with the findings/fixes, and (when enforcing) fails the check to block the merge.
  Runs in **demo mode** out of the box (bundled sample) and switches to **live
  SonarCloud** automatically once a token is configured.

### Enable live SonarCloud + merge blocking

1. Create a free SonarCloud project for this repo and note its **project key**.
2. Update `sonar-project.properties` (`sonar.organization`, `sonar.projectKey`).
3. In the repo settings add:
   - secret **`SONAR_TOKEN`** (SonarCloud token)
   - secret **`GROQ_API_KEY`** (for live LLM rationales/fixes; omit to run mock)
   - variable **`SONAR_PROJECT_KEY`** (same key as above)
   - variable **`GATEKEEPER_ENFORCE`** = `true` to fail the check on a bad gate
4. Add a branch-protection rule on `main` requiring the **GateKeeper** check —
   now a failed gate blocks the merge.

## Roadmap

- [x] **M1** — Multi-agent LangGraph + FastAPI, runs locally against a sample payload
- [x] **M4** — GitHub Actions pipeline: scan → gate → post PR comment → block merge
- [ ] **M2** — Live SonarCloud integration (`/api/issues/search`) + diff-aware triage
- [ ] **M3** — Containerize (Docker/ECR), deploy Lambda + API Gateway via Terraform
- [ ] **M5** — Observability (CloudWatch dashboards/alarms), run history in DynamoDB

---

## Project layout

```
.github/workflows/   ci.yml (lint+tests) and gatekeeper.yml (PR gate)
app/
  main.py            FastAPI app (/health, /review, /webhook/sonar)
  cli.py             CI entrypoint: fetch -> gate -> report -> exit code
  config.py          settings + mock-mode toggle
  models.py          SonarQube + agent-output models, graph state
  llm.py             Groq client wrapper
  agents/
    graph.py         LangGraph wiring + run_review()
    triage.py  security.py  fix_suggest.py  summarizer.py
  sonar/client.py    sample loading + live SonarCloud fetch
samples/             sample SonarQube payload
scripts/run_local.py local runner
sonar-project.properties
tests/               offline (mock-mode) graph + CLI tests
```
