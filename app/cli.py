"""GateKeeper CLI — the entrypoint CI runs on every pull request.

    python -m app.cli [--source auto|sonarcloud|sample|file] [--output report.md]

Resolves findings (live SonarCloud or the bundled sample), runs the agent graph,
writes a Markdown report, and exits non-zero on a failed gate (when enforcing) so
the CI check turns red and branch protection can block the merge.

GitHub Actions integration: writes ``gate``/``source`` to $GITHUB_OUTPUT and the
report to $GITHUB_STEP_SUMMARY when those are present.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.agents.graph import run_review
from app.models import SonarReport
from app.sonar.client import DEFAULT_HOST, fetch_report, load_sample

_DEMO_NOTE = (
    "> ⚠️ **Demo data** — running against the bundled sample payload. "
    "Set `SONAR_TOKEN` + `SONAR_PROJECT_KEY` to gate on live SonarCloud findings.\n\n"
)


def _resolve_source(args: argparse.Namespace) -> str:
    if args.source != "auto":
        return args.source
    has_creds = bool(os.getenv("SONAR_TOKEN")) and bool(
        args.project_key or os.getenv("SONAR_PROJECT_KEY")
    )
    return "sonarcloud" if has_creds else "sample"


def _load_report(args: argparse.Namespace, source: str) -> SonarReport:
    if source == "file":
        if not args.file:
            raise ValueError("--file is required when --source=file")
        return SonarReport.model_validate(json.loads(Path(args.file).read_text(encoding="utf-8")))
    if source == "sonarcloud":
        return fetch_report(
            project_key=args.project_key or os.getenv("SONAR_PROJECT_KEY", ""),
            pull_request=args.pull_request or os.getenv("PR_NUMBER"),
            host=args.host,
        )
    return load_sample()


def _emit_github_outputs(gate: str, source: str, markdown: str) -> None:
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")
    gh_output = os.getenv("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"gate={gate}\n")
            fh.write(f"source={source}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the GateKeeper quality gate.")
    parser.add_argument(
        "--source", choices=["auto", "sonarcloud", "sample", "file"], default="auto"
    )
    parser.add_argument("--file", help="path to a SonarQube issues JSON payload")
    parser.add_argument("--project-key", help="SonarCloud project key")
    parser.add_argument("--pull-request", help="pull request number to scope findings")
    parser.add_argument("--host", default=os.getenv("SONAR_HOST_URL", DEFAULT_HOST))
    parser.add_argument("--output", help="write the Markdown report to this path")
    parser.add_argument("--enforce", dest="enforce", action="store_true", default=None)
    parser.add_argument("--no-enforce", dest="enforce", action="store_false")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    source = _resolve_source(args)
    try:
        report = _load_report(args, source)
        result = run_review(report)
        gate, reason = result.gate, result.reason
        markdown = (_DEMO_NOTE if source == "sample" else "") + result.summary_markdown
    except Exception as exc:  # keep CI green-path: always produce a report to comment
        gate, reason = "ERROR", f"GateKeeper could not evaluate findings: {exc}"
        markdown = f"## ⚠️ GateKeeper — ERROR\n\n_{reason}_\n"

    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    print(markdown)
    _emit_github_outputs(gate, source, markdown)
    print(f"\n>>> GATE: {gate} ({source}) — {reason}", file=sys.stderr)

    enforce = args.enforce
    if enforce is None:
        enforce = os.getenv("GATEKEEPER_ENFORCE", "true").lower() != "false"
    return 1 if (gate == "FAIL" and enforce) else 0


if __name__ == "__main__":
    raise SystemExit(main())
