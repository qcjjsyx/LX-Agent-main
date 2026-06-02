"""Time the deterministic base build of the layered RTL manual workflow."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .event_logger import log_event
    from .manual_cli import _load_dotenv, apply_runtime_env
    from .manual_workflow import PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE
    from .workflows.rtl_manual.workflow import build_base_manual
except ImportError:  # pragma: no cover
    from event_logger import log_event
    from manual_cli import _load_dotenv, apply_runtime_env
    from manual_workflow import PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE
    from workflows.rtl_manual.workflow import build_base_manual


BASE_DIR = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    apply_runtime_env(args)
    run_id = "manual_timing_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    event_logger = (
        (lambda event_type, **payload: log_event(run_id, event_type, **payload))
        if args.log_events
        else None
    )

    started = time.perf_counter()
    error = ""
    result: dict[str, Any] = {}
    try:
        result = build_base_manual(
            project_root=args.project_root,
            rtl_inputs=args.rtl_inputs,
            top_module=args.top_module,
            audience=args.audience,
            evidence_mode=args.evidence_mode,
            enrich_modules=args.enrich_modules,
            force=True,
            event_logger=event_logger,
        )
    except Exception as exc:
        error = str(exc)
        print(f"error: {error}", file=sys.stderr)
    total_seconds = time.perf_counter() - started
    report = build_report(args, run_id, result, total_seconds, error)
    report_paths = write_reports(args, report)
    print_summary(report, report_paths)
    return 0 if not error else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.manual_timing",
        description="Force a deterministic RTL base manual build and measure elapsed time.",
    )
    parser.add_argument("--project-root", default=str(BASE_DIR / "rtl"), help="Project root. Defaults to this repo's rtl sample root.")
    parser.add_argument("--rtl-inputs", default="rtl", help="RTL input path under project root. Defaults to rtl.")
    parser.add_argument("--top-module", default="arm_soc_top", help="Top module name.")
    parser.add_argument("--audience", choices=("newcomer", "maintainer", "reviewer"), default="newcomer")
    parser.add_argument(
        "--evidence-mode",
        choices=(PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE),
        default=PROJECT_EVIDENCE_MODE,
    )
    parser.add_argument("--report-dir", default=str(BASE_DIR / "data" / "logs"), help="Timing report output directory.")
    parser.add_argument("--parser-timeout", type=int, default=0, help="Parser timeout seconds.")
    parser.add_argument("--knowledge-timeout", type=int, default=0, help="Knowledge timeout seconds.")
    parser.add_argument("--enrich-modules", default="", help="Comma-separated Semantic Layer module allowlist.")
    parser.add_argument("--log-events", action="store_true", help="Also write normal event logs.")
    return parser


def build_report(
    args: argparse.Namespace,
    run_id: str,
    result: dict[str, Any],
    total_seconds: float,
    error: str = "",
) -> dict[str, Any]:
    state = result.get("state", {}) if result else {}
    return {
        "schema": "rtl_manual_timing_report",
        "schema_version": "0.2",
        "run_id": run_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "project_root": str(Path(args.project_root).expanduser().resolve()),
            "rtl_inputs": args.rtl_inputs,
            "top_module": args.top_module,
            "audience": args.audience,
            "evidence_mode": args.evidence_mode,
            "enrich_modules": args.enrich_modules,
        },
        "status": "failed" if error else "success",
        "total_seconds": round(total_seconds, 3),
        "stage_results": result.get("stage_results", []) if result else [],
        "artifacts": {
            "base_main": str(result.get("base_main", "")) if result else "",
            "base_modules_dir": str(result.get("base_modules_dir", "")) if result else "",
            "manifest": str(result.get("manifest_path", "")) if result else "",
            "manual_context": state.get("manual_context_dir", ""),
        },
        "error": error,
    }


def write_reports(args: argparse.Namespace, report: dict[str, Any]) -> dict[str, Path]:
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = report["run_id"]
    json_path = report_dir / f"{stem}.json"
    md_path = report_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(report) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        f"# RTL Manual Timing Report: {report['run_id']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Total: {report['total_seconds']}s",
        f"- Top module: `{report['config']['top_module']}`",
        "",
        "## Artifacts",
    ]
    for key, value in report.get("artifacts", {}).items():
        lines.append(f"- {key}: `{value or 'not written'}`")
    if report.get("error"):
        lines.extend(["", "## Error", "", "```text", report["error"], "```"])
    return "\n".join(lines)


def print_summary(report: dict[str, Any], report_paths: dict[str, Path]) -> None:
    print("Timing report")
    print(f"- status: {report['status']}")
    print(f"- total_seconds: {report['total_seconds']}")
    print(f"- json: {report_paths['json']}")
    print(f"- markdown: {report_paths['markdown']}")
    if report.get("error"):
        print(f"- error: {report['error']}")


if __name__ == "__main__":
    raise SystemExit(main())
