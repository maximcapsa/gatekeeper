"""Per-repo gate policy.

Each repository can drop a `.gatekeeper.yml` at its root to tune the gate without
touching GateKeeper itself — this is what makes the App multi-tenant. The file is
fetched at PR time and parsed into a `GatePolicy`; a missing or malformed file falls
back to `DEFAULT_POLICY`, so the gate never breaks on bad config.

Example `.gatekeeper.yml`:

    blocking_severities: [BLOCKER, CRITICAL]
    fail_on_vulnerability: true
    fail_on_security_hotspot: false
    enforce: true            # false = advisory only (a FAIL posts a neutral check)
    ignore_paths:
      - "tests/**"
      - "**/migrations/**"
"""

from __future__ import annotations

from fnmatch import fnmatch

import yaml
from pydantic import BaseModel, field_validator

from app.models import SEVERITY_ORDER, SonarIssue

POLICY_FILE = ".gatekeeper.yml"


class GatePolicy(BaseModel):
    """Tunable gate rules for a single repository."""

    blocking_severities: tuple[str, ...] = ("BLOCKER", "CRITICAL")
    fail_on_vulnerability: bool = True
    fail_on_security_hotspot: bool = False
    ignore_paths: tuple[str, ...] = ()
    # When false, a failed gate is reported but does not block (neutral Check Run).
    enforce: bool = True

    @field_validator("blocking_severities", mode="before")
    @classmethod
    def _normalize_severities(cls, v: object) -> tuple[str, ...]:
        if v is None:
            return ()
        if isinstance(v, str):
            v = [v]
        # Uppercase, keep only severities GateKeeper understands, preserve order.
        return tuple(s.upper() for s in v if str(s).upper() in SEVERITY_ORDER)

    @field_validator("ignore_paths", mode="before")
    @classmethod
    def _coerce_paths(cls, v: object) -> tuple[str, ...]:
        if v is None:
            return ()
        if isinstance(v, str):
            v = [v]
        return tuple(str(p) for p in v)

    def is_ignored(self, issue: SonarIssue) -> bool:
        """True if the issue's file matches any ignore_paths glob."""
        path = _issue_path(issue.component)
        return any(fnmatch(path, pat) for pat in self.ignore_paths)


DEFAULT_POLICY = GatePolicy()


def _issue_path(component: str) -> str:
    """Strip Sonar's `project:` prefix to get the repo-relative file path."""
    return component.split(":", 1)[1] if ":" in component else component


def parse_policy(text: str) -> GatePolicy:
    """Parse `.gatekeeper.yml` contents. Raises on invalid YAML/shape."""
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("policy file must be a YAML mapping")
    known = GatePolicy.model_fields.keys()
    return GatePolicy(**{k: v for k, v in data.items() if k in known})


def load_policy(text: str | None) -> GatePolicy:
    """Best-effort policy load: any problem falls back to DEFAULT_POLICY."""
    if not text:
        return DEFAULT_POLICY
    try:
        return parse_policy(text)
    except Exception:
        return DEFAULT_POLICY
