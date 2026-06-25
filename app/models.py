"""Domain models: SonarQube findings, agent outputs, and the LangGraph state."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

Severity = Literal["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]
IssueType = Literal["BUG", "VULNERABILITY", "CODE_SMELL", "SECURITY_HOTSPOT"]

# Lower number = more urgent. Used for deterministic ranking.
SEVERITY_ORDER: dict[str, int] = {
    "BLOCKER": 0,
    "CRITICAL": 1,
    "MAJOR": 2,
    "MINOR": 3,
    "INFO": 4,
}

SECURITY_TYPES = {"VULNERABILITY", "SECURITY_HOTSPOT"}


class SonarIssue(BaseModel):
    """A single finding, shaped like SonarQube's /api/issues/search payload."""

    key: str
    rule: str
    severity: Severity
    type: IssueType
    component: str
    message: str
    line: int | None = None
    status: str = "OPEN"
    effort: str | None = None


class SonarReport(BaseModel):
    project: str
    branch: str | None = None
    pull_request: str | None = Field(default=None, alias="pullRequest")
    issues: list[SonarIssue] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class TriagedIssue(BaseModel):
    issue: SonarIssue
    priority: int  # 0 = most urgent
    rationale: str


class FixSuggestion(BaseModel):
    issue_key: str
    component: str
    summary: str
    patch: str


class ReviewResult(BaseModel):
    project: str
    gate: Literal["PASS", "FAIL"]
    reason: str
    summary_markdown: str
    triaged: list[TriagedIssue] = Field(default_factory=list)
    security_findings: list[TriagedIssue] = Field(default_factory=list)
    fix_suggestions: list[FixSuggestion] = Field(default_factory=list)


class GraphState(TypedDict, total=False):
    """Shared state threaded through the LangGraph nodes."""

    report: SonarReport
    triaged: list[TriagedIssue]
    security_findings: list[TriagedIssue]
    fix_suggestions: list[FixSuggestion]
    gate: str
    reason: str
    summary_markdown: str
