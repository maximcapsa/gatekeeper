"""Run the GateKeeper graph against the bundled sample payload and print the result.

    python scripts/run_local.py

Runs in mock mode if GROQ_API_KEY is unset (still exercises the full graph).
"""

from __future__ import annotations

import sys
from pathlib import Path

# The Markdown output contains emoji (rendered in GitHub PR comments). Ensure the
# console can print UTF-8 even on a legacy Windows code page.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import run_review  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.sonar.client import load_sample  # noqa: E402


def main() -> int:
    mode = "MOCK (no LLM calls)" if get_settings().use_mock else "LIVE (Groq)"
    report = load_sample()
    print(f"Mode: {mode}")
    print(f"Project: {report.project} | PR #{report.pull_request} | {len(report.issues)} issues\n")

    result = run_review(report)
    print(result.summary_markdown)
    print(f"\n>>> GATE: {result.gate} — {result.reason}")
    return 1 if result.gate == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
