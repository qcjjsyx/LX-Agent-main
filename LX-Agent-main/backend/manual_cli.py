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
    from .manual_intent import ManualIntent
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
    from manual_intent import ManualIntent
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
STAGE_ORDER = MANUAL_STAGE_ORDER


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    apply_runtime_env(args) ## 配置运行时间

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
    event_logger = build_event_logger(args)

    exit_code = run_cli_workflow(args, state, client, model, event_logger) ## cli 流程入口
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
        or os.getenv("DEEPSEEK_MODEL")
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
    intent = build_manual_intent_from_args(args, force_full_run=bool(args.force))
    plan = build_manual_plan(intent, None, BASE_DIR)
    if plan.confirmation_required:
        raise ValueError(plan.confirmation_message)
    state = apply_manual_plan_to_state(_ensure_state(None), plan)
    state["auto_run"] = False
    state["manual_output_override"] = str(Path(args.output).expanduser().resolve()) if args.output else ""
    state["completed_stages"] = []
    state["last_error"] = ""
    return state


def build_manual_intent_from_args(args: argparse.Namespace, force_full_run: bool = False) -> ManualIntent:
    project_root = str(Path(args.project_root).expanduser().resolve())
    start_stage = getattr(args, "start_stage", "references") or "references"
    if force_full_run and start_stage == "references":
        rerun_policy = "clean_all_and_run"
    elif force_full_run:
        rerun_policy = "force_from_stage"
    else:
        rerun_policy = "reuse_valid_artifacts"

    return ManualIntent(
        intent="rerun_workflow" if force_full_run else "generate_manual",
        project_root=project_root,
        rtl_inputs=args.rtl_inputs,
        top_module=args.top_module,
        audience=args.audience,
        evidence_mode=args.evidence_mode,
        start_stage=start_stage,
        rerun_policy=rerun_policy,
        auto_run=False,
        semantic_enrichment=True,
        enrich_modules=args.enrich_modules,
        manual_generation_mode=args.manual_generation_mode,
        llm_module_page_scope=args.llm_module_page_scope,
        llm_module_page_limit=args.llm_module_page_limit,
        llm_module_page_allowlist=args.llm_module_page_allowlist,
    )


def build_event_logger(args: argparse.Namespace):
    if not args.log_events:
        return None
    run_id = "manual_cli_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    return lambda event_type, **payload: log_event(run_id, event_type, **payload)


## 逐阶段进行，开始阶段由命令行控制，每个阶段的具体执行流程在
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
    print(f"- manual_generation_mode: {state.get('manual_generation_mode', 'deterministic')}")
    print(f"- llm_module_page_scope: {state.get('llm_module_page_scope', 'top_and_direct')}")
    print(f"- llm_module_page_limit: {state.get('llm_module_page_limit', 20)}")
    if state.get("llm_module_page_allowlist"):
        print(f"- llm_module_page_allowlist: {state.get('llm_module_page_allowlist')}")
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
        "手册生成模式：",
        "LLM 润色状态：",
        "回退原因：",
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
