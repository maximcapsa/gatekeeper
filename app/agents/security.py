"""Security agent.

Isolates the security-relevant subset of triaged findings (vulnerabilities and
security hotspots). Pure, deterministic filtering — cheap and reliable, no LLM
call needed for milestone 1.
"""

from __future__ import annotations

from app.models import SECURITY_TYPES, GraphState, TriagedIssue


def security_node(state: GraphState) -> GraphState:
    triaged: list[TriagedIssue] = state.get("triaged", [])
    findings = [t for t in triaged if t.issue.type in SECURITY_TYPES]
    return {"security_findings": findings}
