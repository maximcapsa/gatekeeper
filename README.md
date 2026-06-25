# GateKeeper — AI code-quality gate for pull requests

GateKeeper turns raw **SonarQube / SonarCloud** static-analysis findings into an
actionable PR review and a merge **pass/fail gate**. A **LangGraph** multi-agent
system — triage, security, fix-suggestion, and summarizer agents — runs behind a
**FastAPI** service and is wired into CI so every pull request gets reviewed
automatically.

Built as a DevOps portfolio project: CI/CD, a real quality gate, containerization,
Infrastructure-as-Code, and practical multi-agent AI — designed to run on the
**AWS Free Tier** with a **free Groq** LLM backend.

> **Status:** Milestone 1 complete — the multi-agent graph runs locally end-to-end
> against a sample SonarQube payload (and offline in mock mode). AWS deployment and
> live SonarCloud/CI wiring land in later milestones (see [Roadmap](#roadmap)).

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

## Roadmap

- [x] **M1** — Multi-agent LangGraph + FastAPI, runs locally against a sample payload
- [ ] **M2** — Live SonarCloud integration (`/api/issues/search`) + diff-aware triage
- [ ] **M3** — Containerize (Docker/ECR), deploy Lambda + API Gateway via Terraform
- [ ] **M4** — GitHub Actions pipeline: scan → gate → post PR comment → block merge
- [ ] **M5** — Observability (CloudWatch dashboards/alarms), run history in DynamoDB

---

## Project layout

```
app/
  main.py            FastAPI app (/health, /review, /webhook/sonar)
  config.py          settings + mock-mode toggle
  models.py          SonarQube + agent-output models, graph state
  llm.py             Groq client wrapper
  agents/
    graph.py         LangGraph wiring + run_review()
    triage.py  security.py  fix_suggest.py  summarizer.py
  sonar/client.py    payload loading/parsing
samples/             sample SonarQube payload
scripts/run_local.py CLI runner
tests/               offline (mock-mode) graph tests
```
