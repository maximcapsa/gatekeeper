"""Triage agent.

Ranks raw SonarQube issues deterministically (by severity, then location) so the
ordering is reproducible and free, then asks the LLM for a one-line rationale per
issue. In mock mode the rationale is generated locally.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm import chat_json
from app.models import SEVERITY_ORDER, GraphState, SonarIssue, TriagedIssue

SYSTEM = (
    "You are a senior code reviewer triaging static-analysis findings. "
    "Given one finding, explain in a single concise sentence why it matters and "
    "what the risk is. Respond as JSON: {\"rationale\": \"...\"}."
)


def _rank(issues: list[SonarIssue]) -> list[SonarIssue]:
    return sorted(
        issues,
        key=lambda i: (SEVERITY_ORDER.get(i.severity, 99), i.component, i.line or 0),
    )


def _mock_rationale(issue: SonarIssue) -> str:
    return (
        f"{issue.severity.title()} {issue.type.replace('_', ' ').lower()} "
        f"in {issue.component}: {issue.message}"
    )


def _user_prompt(issue: SonarIssue) -> str:
    loc = f"{issue.component}:{issue.line}" if issue.line else issue.component
    return (
        f"Severity: {issue.severity}\nType: {issue.type}\nRule: {issue.rule}\n"
        f"Location: {loc}\nMessage: {issue.message}"
    )


def triage_node(state: GraphState) -> GraphState:
    settings = get_settings()
    report = state["report"]
    open_issues = [i for i in report.issues if i.status.upper() != "RESOLVED"]
    ranked = _rank(open_issues)

    triaged: list[TriagedIssue] = []
    for priority, issue in enumerate(ranked):
        rationale = _mock_rationale(issue)
        if not settings.use_mock:
            try:
                data = chat_json(SYSTEM, _user_prompt(issue), settings.model_triage)
                rationale = data.get("rationale") or rationale
            except Exception:
                pass  # fall back to the deterministic rationale on any LLM error
        triaged.append(TriagedIssue(issue=issue, priority=priority, rationale=rationale))

    return {"triaged": triaged}
