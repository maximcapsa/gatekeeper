"""Fix-suggestion agent.

For the top-N most urgent blocking issues, drafts a concrete remediation. This is
the one node that benefits from a stronger model, so it routes to ``model_fix``.
In mock mode it emits a templated suggestion so the pipeline stays runnable offline.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm import chat_json
from app.models import FixSuggestion, GraphState, TriagedIssue

SYSTEM = (
    "You are a staff engineer fixing static-analysis findings. Given one finding, "
    "produce a short remediation. Respond as JSON with exactly: "
    '{"summary": "one sentence on the fix", "patch": "a minimal code or config '
    'change as a unified-diff-style snippet"}.'
)


def _is_blocking(t: TriagedIssue, blocking: tuple[str, ...]) -> bool:
    return t.issue.severity in blocking


def _mock_fix(t: TriagedIssue) -> FixSuggestion:
    return FixSuggestion(
        issue_key=t.issue.key,
        component=t.issue.component,
        summary=f"Address {t.issue.rule} ({t.issue.severity}) at {t.issue.component}.",
        patch=(
            f"# {t.issue.component}:{t.issue.line or '?'}\n"
            f"# {t.issue.message}\n"
            "- <vulnerable / non-compliant line>\n"
            "+ <remediated line>"
        ),
    )


def _user_prompt(t: TriagedIssue) -> str:
    i = t.issue
    loc = f"{i.component}:{i.line}" if i.line else i.component
    return f"Rule: {i.rule}\nSeverity: {i.severity}\nLocation: {loc}\nMessage: {i.message}"


def fix_suggest_node(state: GraphState) -> GraphState:
    settings = get_settings()
    triaged: list[TriagedIssue] = state.get("triaged", [])
    blocking = [t for t in triaged if _is_blocking(t, settings.blocking_severities)]
    targets = blocking[: settings.max_fix_suggestions]

    suggestions: list[FixSuggestion] = []
    for t in targets:
        fix = _mock_fix(t)
        if not settings.use_mock:
            data = chat_json(SYSTEM, _user_prompt(t), settings.model_fix)
            fix = FixSuggestion(
                issue_key=t.issue.key,
                component=t.issue.component,
                summary=data.get("summary") or fix.summary,
                patch=data.get("patch") or fix.patch,
            )
        suggestions.append(fix)

    return {"fix_suggestions": suggestions}
