"""Command line entrypoint for the RTL manual workflow.

This module intentionally reuses ``manual_workflow`` instead of duplicating the
pipeline logic from the Flask app.  It is meant for fast local debugging:

    python -m backend.manual_cli --top-module arm_soc_top
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .event_logger import log_event
    from .manual_workflow import (
        PROJECT_EVIDENCE_MODE,
        READING_PATH_EVIDENCE_MODE,
        _artifact_base_from_parser,
        _ensure_state,
        _run_current_stage,
        _select_parser_dir,
    )
except ImportError:  # pragma: no cover - supports direct script execution
    from event_logger import log_event
    from manual_workflow import (
        PROJECT_EVIDENCE_MODE,
        READING_PATH_EVIDENCE_MODE,
        _artifact_base_from_parser,
        _ensure_state,
        _run_current_stage,
        _select_parser_dir,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
STAGE_ORDER = (
    "references",
    "parser",
    "knowledge",
    "evidence",
    "source_review",
    "outline",
    "chapter_plan",
    "manual",
    "review",
)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    apply_runtime_env(args)

    try:
        client, model = build_model_client(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    state = build_initial_state(args)
    event_logger = build_event_logger(args)

    exit_code = run_cli_workflow(args, state, client, model, event_logger)
    maybe_write_state(args, state)
    print_final_summary(state)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.manual_cli",
        description="Run the RTL manual generation workflow without starting app.py.",
    )
    parser.add_argument("--project-root", default=str(BASE_DIR), help="RTL project root. Defaults to this repo root.")
    parser.add_argument("--rtl-inputs", default="rtl", help="RTL input directory under project root. Defaults to rtl.")
    parser.add_argument("--top-module", required=True, help="Top module name, for example arm_soc_top.")
    parser.add_argument(
        "--audience",
        choices=("newcomer", "maintainer", "reviewer"),
        default="newcomer",
        help="Manual audience profile.",
    )
    parser.add_argument(
        "--evidence-mode",
        choices=(PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE),
        default=PROJECT_EVIDENCE_MODE,
        help="Evidence selection mode.",
    )
    parser.add_argument(
        "--enrich-modules",
        default="",
        help="Comma-separated Semantic Layer module allowlist. Empty means all modules selected by the pipeline.",
    )
    parser.add_argument("--output", default="", help="Markdown manual output path. Defaults to docs/manuals/<top>_generated.md.")
    parser.add_argument("--force", action="store_true", help="Regenerate artifacts instead of reusing existing ones.")
    parser.add_argument(
        "--model",
        default="",
        help="Model for source_review. Defaults to MANUAL_WORKFLOW_MODEL, MANUAL_IR_ENRICH_MODEL, OPENAI_MODEL, or deepseek-chat.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="OpenAI-compatible base URL. Defaults to OPENAI_BASE_URL, DEEPSEEK_BASE_URL, LLM_BASE_URL, or DeepSeek.",
    )
    parser.add_argument("--api-key", default="", help="API key. Defaults to OPENAI_API_KEY, DEEPSEEK_API_KEY, or LLM_API_KEY.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Do not create a model client for source_review. Flagged claims stay as evidence gaps.",
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="Fail fast if no source_review model client can be created.",
    )
    parser.add_argument(
        "--start-stage",
        choices=STAGE_ORDER,
        default="references",
        help="Start from a workflow stage. Use evidence/source_review/manual only when prerequisite artifacts already exist.",
    )
    parser.add_argument(
        "--state-out",
        default="",
        help="Optional JSON path for saving final workflow state.",
    )
    parser.add_argument(
        "--parser-timeout",
        type=int,
        default=0,
        help="Parser tool timeout in seconds. Defaults to RTL_MANUAL_PARSER_TIMEOUT or 220.",
    )
    parser.add_argument(
        "--knowledge-timeout",
        type=int,
        default=0,
        help="Knowledge pipeline timeout in seconds. Defaults to RTL_MANUAL_KNOWLEDGE_TIMEOUT or 600.",
    )
    parser.add_argument("--log-events", action="store_true", help="Write CLI workflow events to data/logs.")
    parser.add_argument("--quiet", action="store_true", help="Print only compact stage progress and final artifact paths.")
    parser.add_argument("--verbose", action="store_true", help="Print full stage replies.")
    return parser


def _load_dotenv() -> None:
    try:
        import dotenv
    except ImportError:
        return
    dotenv.load_dotenv(BASE_DIR / ".env")
    dotenv.load_dotenv()


def apply_runtime_env(args: argparse.Namespace) -> None:
    if args.parser_timeout and args.parser_timeout > 0:
        os.environ["RTL_MANUAL_PARSER_TIMEOUT"] = str(args.parser_timeout)
    if args.knowledge_timeout and args.knowledge_timeout > 0:
        os.environ["RTL_MANUAL_KNOWLEDGE_TIMEOUT"] = str(args.knowledge_timeout)
        os.environ.setdefault("RTL_MANUAL_KNOWLEDGE_WRAPPER_TIMEOUT", str(args.knowledge_timeout + 120))


def build_model_client(args: argparse.Namespace):
    model = (
        args.model
        or os.getenv("MANUAL_WORKFLOW_MODEL")
        or os.getenv("MANUAL_IR_ENRICH_MODEL")
        or os.getenv("OPENAI_MODEL")
        or "deepseek-chat"
    )
    if args.no_llm:
        if args.require_llm:
            raise RuntimeError("--no-llm cannot be combined with --require-llm")
        return None, None

    api_key = args.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = (
        args.base_url
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or "https://api.deepseek.com"
    )
    if not api_key:
        if args.require_llm:
            raise RuntimeError("missing API key; set OPENAI_API_KEY, DEEPSEEK_API_KEY, LLM_API_KEY, or pass --api-key")
        print(
            "warning: no API key found; source_review will mark flagged claims as evidence gaps. "
            "Pass --require-llm to fail instead.",
            file=sys.stderr,
        )
        return None, None

    try:
        from openai import OpenAI
    except ImportError as exc:
        if args.require_llm:
            raise RuntimeError("openai package is required for source_review") from exc
        print("warning: openai package is missing; source_review will fall back to evidence gaps.", file=sys.stderr)
        return None, None

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs), model


def build_initial_state(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    state = _ensure_state(None)
    state.update(
        {
            "active": True,
            "stage": args.start_stage,
            "project_root": str(project_root),
            "rtl_inputs": args.rtl_inputs,
            "top_module": args.top_module,
            "audience": args.audience,
            "evidence_mode": args.evidence_mode,
            "auto_run": False,
            "force_regenerate": bool(args.force),
            "semantic_enrichment": True,
            "enrich_modules": args.enrich_modules,
            "manual_output_override": str(Path(args.output).expanduser().resolve()) if args.output else "",
            "completed_stages": [],
            "last_error": "",
        }
    )
    parser_dir = _select_parser_dir(state["project_root"])
    artifact_base = _artifact_base_from_parser(state["project_root"], parser_dir)
    state["parser_dir"] = str(parser_dir)
    state["knowledge_dir"] = str(artifact_base / "knowledge_ir" / state["top_module"])
    state["manual_context_dir"] = str(artifact_base / "manual_context" / state["top_module"])
    return state


def build_event_logger(args: argparse.Namespace):
    if not args.log_events:
        return None
    run_id = "manual_cli_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    return lambda event_type, **payload: log_event(run_id, event_type, **payload)


def run_cli_workflow(args: argparse.Namespace, state: dict[str, Any], client, model, event_logger) -> int:
    print_run_header(args, state, model)
    for index in range(len(STAGE_ORDER) + 2):
        stage_before = state.get("stage", "")
        if stage_before in {"done", "cancelled"}:
            break
        if stage_before not in STAGE_ORDER:
            state["last_error"] = f"unknown workflow stage: {stage_before}"
            print(f"error: {state['last_error']}", file=sys.stderr)
            return 1

        reply = _run_current_stage(
            state,
            BASE_DIR,
            client,
            model,
            "CLI workflow run",
            event_logger,
        )
        print_stage_result(args, index + 1, stage_before, state, reply)

        if state.get("last_error"):
            return 1
        if state.get("stage") == stage_before:
            state["last_error"] = f"stage did not advance: {stage_before}"
            print(f"error: {state['last_error']}", file=sys.stderr)
            return 1
    return 0 if state.get("stage") == "done" else 1


def print_run_header(args: argparse.Namespace, state: dict[str, Any], model: str | None) -> None:
    if args.quiet:
        return
    print("RTL manual workflow CLI")
    print(f"- project_root: {state['project_root']}")
    print(f"- rtl_inputs: {state['rtl_inputs']}")
    print(f"- top_module: {state['top_module']}")
    print(f"- start_stage: {state['stage']}")
    print(f"- force_regenerate: {state['force_regenerate']}")
    print(f"- source_review_model: {model or 'disabled'}")
    print(f"- parser_timeout: {os.getenv('RTL_MANUAL_PARSER_TIMEOUT') or 'default'}")
    print(f"- knowledge_timeout: {os.getenv('RTL_MANUAL_KNOWLEDGE_TIMEOUT') or 'default'}")
    if state.get("manual_output_override"):
        print(f"- output: {state['manual_output_override']}")
    print("")


def print_stage_result(args: argparse.Namespace, index: int, stage_before: str, state: dict[str, Any], reply: str) -> None:
    if args.verbose:
        print(reply)
        print("")
        return

    title = extract_reply_title(reply)
    status = "failed" if state.get("last_error") else "done"
    print(f"[{index}] {stage_before} -> {state.get('stage', '')}: {status} ({title})")
    if args.quiet:
        return
    for line in extract_important_lines(reply):
        print(f"    {line}")
    if state.get("last_error"):
        print(f"    error: {state['last_error']}")


def extract_reply_title(reply: str) -> str:
    for line in (reply or "").splitlines():
        line = line.strip()
        if line.startswith("## "):
            return line[3:].strip()
    return "stage completed"


def extract_important_lines(reply: str) -> list[str]:
    keep_prefixes = (
        "Parser 产物目录：",
        "parser 产物目录：",
        "Knowledge IR 目录：",
        "Manual Context 目录：",
        "源码复核报告：",
        "保存路径：",
        "模块页目录：",
        "手册路径：",
        "审查报告路径：",
    )
    lines = []
    for line in (reply or "").splitlines():
        text = line.strip("- ").strip()
        if any(text.startswith(prefix) for prefix in keep_prefixes):
            lines.append(text)
    return lines[:8]


def maybe_write_state(args: argparse.Namespace, state: dict[str, Any]) -> None:
    if not args.state_out:
        return
    path = Path(args.state_out).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"state saved: {path}")


def print_final_summary(state: dict[str, Any]) -> None:
    print("")
    print("Final state")
    print(f"- stage: {state.get('stage', '')}")
    print(f"- manual_context: {state.get('manual_context_dir', '')}")
    print(f"- source_review: {state.get('source_review_output_path', '') or 'not written'}")
    print(f"- manual: {state.get('manual_output_path', '') or 'not written'}")
    print(f"- module_pages: {state.get('manual_module_pages_dir', '') or 'not written'}")
    print(f"- review: {state.get('review_output_path', '') or 'not written'}")
    if state.get("last_error"):
        print(f"- error: {state['last_error']}")


if __name__ == "__main__":
    raise SystemExit(main())
