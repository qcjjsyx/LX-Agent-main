"""Run a full RTL manual regeneration and record per-stage timings.

Default layout matches this repository:

    project_root = repo root
    rtl_inputs   = rtl
    source dir   = rtl/rtl, detected by the parser wrapper

Run:

    python -m backend.manual_timing --top-module arm_soc_top
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .event_logger import log_event
    from .manual_cli import _load_dotenv, apply_runtime_env, build_manual_intent_from_args, build_model_client
    from .manual_planner import build_manual_plan
    from .manual_workflow import (
        MANUAL_GENERATION_MODES,
        MANUAL_STAGE_ORDER,
        PROJECT_EVIDENCE_MODE,
        READING_PATH_EVIDENCE_MODE,
        apply_manual_plan_to_state,
        _ensure_state,
        _run_current_stage,
    )
except ImportError:  # pragma: no cover - supports direct script execution
    from event_logger import log_event
    from manual_cli import _load_dotenv, apply_runtime_env, build_manual_intent_from_args, build_model_client
    from manual_planner import build_manual_plan
    from manual_workflow import (
        MANUAL_GENERATION_MODES,
        MANUAL_STAGE_ORDER,
        PROJECT_EVIDENCE_MODE,
        READING_PATH_EVIDENCE_MODE,
        apply_manual_plan_to_state,
        _ensure_state,
        _run_current_stage,
    )


BASE_DIR = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    apply_runtime_env(args)

    try:
        client, model = build_model_client(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        state = build_initial_state(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    run_id = "manual_timing_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    event_logger = (
        (lambda event_type, **payload: log_event(run_id, event_type, **payload))
        if args.log_events
        else None
    )

    print_header(args, state, model, run_id)
    started = time.perf_counter()
    timings: list[dict[str, Any]] = []

    for index in range(len(MANUAL_STAGE_ORDER) + 2):
        stage = state.get("stage", "")
        if stage in {"done", "cancelled"}:
            break
        if stage not in MANUAL_STAGE_ORDER:
            state["last_error"] = f"unknown workflow stage: {stage}"
            print(f"error: {state['last_error']}", file=sys.stderr)
            break

        item = run_timed_stage(index + 1, stage, state, client, model, event_logger)
        timings.append(item)
        print_stage_timing(item)

        if state.get("last_error"):
            break
        if state.get("stage") == stage:
            state["last_error"] = f"stage did not advance: {stage}"
            print(f"error: {state['last_error']}", file=sys.stderr)
            break

    total_seconds = time.perf_counter() - started
    report = build_report(args, run_id, state, timings, total_seconds)
    report_paths = write_reports(args, report)
    print_summary(report, report_paths)
    return 0 if state.get("stage") == "done" and not state.get("last_error") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.manual_timing",
        description="Force a full RTL manual regeneration and measure every workflow stage.",
    )
    parser.add_argument("--project-root", default=str(BASE_DIR), help="Project root. Defaults to this repo root.")
    parser.add_argument("--rtl-inputs", default="rtl", help="RTL input path under project root. Defaults to rtl.")
    parser.add_argument("--top-module", default="arm_soc_top", help="Top module name.")
    parser.add_argument("--audience", choices=("newcomer", "maintainer", "reviewer"), default="newcomer")
    parser.add_argument(
        "--evidence-mode",
        choices=(PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE),
        default=PROJECT_EVIDENCE_MODE,
        help="Evidence selection mode.",
    )
    parser.add_argument("--output", default="", help="Optional manual output path.")
    parser.add_argument("--report-dir", default=str(BASE_DIR / "data" / "logs"), help="Timing report output directory.")
    parser.add_argument(
        "--manual-generation-mode",
        choices=tuple(sorted(MANUAL_GENERATION_MODES)),
        default="deterministic",
        help=(
            "Manual generation mode. deterministic keeps current renderer; "
            "llm_polish polishes the main manual with LLM after deterministic rendering."
        ),
    )
    parser.add_argument(
        "--llm-module-page-scope",
        choices=("none", "top_only", "top_and_direct", "all", "allowlist"),
        default="top_and_direct",
        help="Which module pages should be polished by LLM when page polish is enabled.",
    )
    parser.add_argument(
        "--llm-module-page-limit",
        type=int,
        default=20,
        help="Maximum number of module pages to polish with LLM.",
    )
    parser.add_argument(
        "--llm-module-page-allowlist",
        default="",
        help="Comma-separated module names to polish when scope=allowlist.",
    )
    parser.add_argument("--parser-timeout", type=int, default=0, help="Parser timeout seconds.")
    parser.add_argument("--knowledge-timeout", type=int, default=0, help="Knowledge timeout seconds.")
    parser.add_argument("--no-llm", action="store_true", help="Disable source_review model calls.")
    parser.add_argument("--require-llm", action="store_true", help="Fail if source_review model client is unavailable.")
    parser.add_argument("--model", default="", help="Source review model override.")
    parser.add_argument("--base-url", default="", help="OpenAI-compatible base URL override.")
    parser.add_argument("--api-key", default="", help="API key override.")
    parser.add_argument("--enrich-modules", default="", help="Comma-separated Semantic Layer module allowlist.")
    parser.add_argument("--log-events", action="store_true", help="Also write normal event logs.")
    return parser


def build_initial_state(args: argparse.Namespace) -> dict[str, Any]:
    intent = build_manual_intent_from_args(args, force_full_run=True)
    plan = build_manual_plan(intent, None, BASE_DIR)
    if plan.confirmation_required:
        raise ValueError(plan.confirmation_message)
    state = apply_manual_plan_to_state(_ensure_state(None), plan)
    state["auto_run"] = False
    state["manual_output_override"] = str(Path(args.output).expanduser().resolve()) if args.output else ""
    state["completed_stages"] = []
    state["last_error"] = ""
    return state


def run_timed_stage(index, stage, state, client, model, event_logger):
    started_wall = datetime.now().isoformat(timespec="seconds")
    started = time.perf_counter()
    reply = _run_current_stage(
        state,
        BASE_DIR,
        client,
        model,
        "full timing regeneration",
        event_logger,
    )
    elapsed = time.perf_counter() - started
    return {
        "index": index,
        "stage": stage,
        "next_stage": state.get("stage", ""),
        "status": "failed" if state.get("last_error") else "done",
        "seconds": round(elapsed, 3),
        "started_at": started_wall,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "title": extract_reply_title(reply),
        "important_lines": extract_important_lines(reply),
        "error": state.get("last_error", ""),
    }


def extract_reply_title(reply: str) -> str:
    for line in (reply or "").splitlines():
        text = line.strip()
        if text.startswith("## "):
            return text[3:].strip()
    return "stage completed"


def extract_important_lines(reply: str) -> list[str]:
    prefixes = (
        "Parser 产物目录：",
        "parser 产物目录：",
        "Knowledge IR 目录：",
        "Manual Context 目录：",
        "源码复核报告：",
        "保存路径：",
        "模块页目录：",
        "手册生成模式：",
        "LLM 润色状态：",
        "主手册整篇润色状态：",
        "主手册章节 LLM：",
        "模块页 LLM 润色：",
        "回退原因：",
        "手册路径：",
        "审查报告路径：",
    )
    lines = []
    for line in (reply or "").splitlines():
        text = line.strip("- ").strip()
        if any(text.startswith(prefix) for prefix in prefixes):
            lines.append(text)
    return lines[:10]


def build_report(args, run_id, state, timings, total_seconds):
    return {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "passed" if state.get("stage") == "done" and not state.get("last_error") else "failed",
        "total_seconds": round(total_seconds, 3),
        "config": {
            "project_root": state.get("project_root"),
            "rtl_inputs": state.get("rtl_inputs"),
            "top_module": state.get("top_module"),
            "force_regenerate": True,
            "parser_timeout": os.getenv("RTL_MANUAL_PARSER_TIMEOUT") or "default",
            "knowledge_timeout": os.getenv("RTL_MANUAL_KNOWLEDGE_TIMEOUT") or "default",
            "semantic_workers": os.getenv("RTL_MANUAL_SEMANTIC_WORKERS") or "default",
            "source_review_llm": not args.no_llm,
            "manual_generation_mode": state.get("manual_generation_mode", "deterministic"),
            "llm_module_page_scope": state.get("llm_module_page_scope", "top_and_direct"),
            "llm_module_page_limit": state.get("llm_module_page_limit", 20),
            "llm_module_page_allowlist": state.get("llm_module_page_allowlist", ""),
        },
        "timings": timings,
        "artifacts": {
            "parser_dir": state.get("parser_dir", ""),
            "knowledge_dir": state.get("knowledge_dir", ""),
            "manual_context_dir": state.get("manual_context_dir", ""),
            "source_review": state.get("source_review_output_path", ""),
            "manual": state.get("manual_output_path", ""),
            "module_pages": state.get("manual_module_pages_dir", ""),
            "review": state.get("review_output_path", ""),
        },
        "last_error": state.get("last_error", ""),
    }


def write_reports(args, report):
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{report['run_id']}.json"
    md_path = report_dir / f"{report['run_id']}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown_report(report) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def render_markdown_report(report):
    lines = [
        f"# RTL Manual Timing Report: {report['run_id']}",
        "",
        f"- Status: `{report['status']}`",
        f"- Total seconds: `{report['total_seconds']}`",
        f"- Project root: `{report['config']['project_root']}`",
        f"- RTL inputs: `{report['config']['rtl_inputs']}`",
        f"- Top module: `{report['config']['top_module']}`",
        "",
        "| # | Stage | Status | Seconds | Next |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for item in report["timings"]:
        lines.append(
            f"| {item['index']} | `{item['stage']}` | `{item['status']}` | "
            f"{item['seconds']} | `{item['next_stage']}` |"
        )
    lines.extend(["", "## Artifacts"])
    for key, value in report["artifacts"].items():
        lines.append(f"- {key}: `{value or 'not written'}`")
    if report.get("last_error"):
        lines.extend(["", "## Last Error", "", "```text", report["last_error"], "```"])
    return "\n".join(lines)


def print_header(args, state, model, run_id):
    print("Full RTL manual regeneration timing")
    print(f"- run_id: {run_id}")
    print(f"- project_root: {state['project_root']}")
    print(f"- rtl_inputs: {state['rtl_inputs']}  (source is expected at rtl/rtl for this repo)")
    print(f"- top_module: {state['top_module']}")
    print(f"- force_regenerate: true")
    print(f"- manual_generation_mode: {state.get('manual_generation_mode', 'deterministic')}")
    print(f"- llm_module_page_scope: {state.get('llm_module_page_scope', 'top_and_direct')}")
    print(f"- llm_module_page_limit: {state.get('llm_module_page_limit', 20)}")
    if state.get("llm_module_page_allowlist"):
        print(f"- llm_module_page_allowlist: {state.get('llm_module_page_allowlist')}")
    print(f"- source_review_model: {model or 'disabled'}")
    print(f"- report_dir: {Path(args.report_dir).expanduser().resolve()}")
    print("")


def print_stage_timing(item):
    print(
        f"[{item['index']}] {item['stage']} -> {item['next_stage']}: "
        f"{item['status']} / {item['seconds']}s ({item['title']})"
    )
    for line in item.get("important_lines", []):
        print(f"    {line}")
    if item.get("error"):
        print(f"    error: {item['error']}")


def print_summary(report, report_paths):
    print("")
    print("Timing summary")
    print(f"- status: {report['status']}")
    print(f"- total_seconds: {report['total_seconds']}")
    for item in report["timings"]:
        print(f"- {item['stage']}: {item['seconds']}s")
    print(f"- json_report: {report_paths['json']}")
    print(f"- markdown_report: {report_paths['markdown']}")
    print(f"- manual: {report['artifacts']['manual'] or 'not written'}")
    print(f"- review: {report['artifacts']['review'] or 'not written'}")


if __name__ == "__main__":
    raise SystemExit(main())
