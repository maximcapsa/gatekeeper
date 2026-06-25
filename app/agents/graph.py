"""LangGraph orchestration.

    START -> triage -> security -> (fix_suggest?) -> summarizer -> END

The fix-suggestion node is skipped via a conditional edge when there are no
blocking issues, so we don't spend the stronger model on clean PRs.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.fix_suggest import fix_suggest_node
from app.agents.security import security_node
from app.agents.summarizer import summarizer_node
from app.agents.triage import triage_node
from app.config import get_settings
from app.models import GraphState, ReviewResult, SonarReport


def _needs_fix(state: GraphState) -> str:
    blocking = get_settings().blocking_severities
    if any(t.issue.severity in blocking for t in state.get("triaged", [])):
        return "fix"
    return "skip"


def _build():
    g = StateGraph(GraphState)
    g.add_node("triage", triage_node)
    g.add_node("security", security_node)
    g.add_node("fix_suggest", fix_suggest_node)
    g.add_node("summarizer", summarizer_node)

    g.add_edge(START, "triage")
    g.add_edge("triage", "security")
    g.add_conditional_edges(
        "security", _needs_fix, {"fix": "fix_suggest", "skip": "summarizer"}
    )
    g.add_edge("fix_suggest", "summarizer")
    g.add_edge("summarizer", END)
    return g.compile()


_APP = None


def get_app():
    """Compiled graph (built once, reused)."""
    global _APP
    if _APP is None:
        _APP = _build()
    return _APP


def run_review(report: SonarReport) -> ReviewResult:
    final: GraphState = get_app().invoke({"report": report})
    return ReviewResult(
        project=report.project,
        gate=final["gate"],
        reason=final["reason"],
        summary_markdown=final["summary_markdown"],
        triaged=final.get("triaged", []),
        security_findings=final.get("security_findings", []),
        fix_suggestions=final.get("fix_suggestions", []),
    )
