"""Command line implementation for the layered RTL manual workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from ...event_logger import log_event
    from ...manual_workflow import PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE
    from ..runtime import WorkflowRuntime
    from ..types import WorkflowContext, WorkflowActionResult
except ImportError:  # pragma: no cover - supports direct script execution via backend/manual_cli.py
    from event_logger import log_event
    from manual_workflow import PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE
    from workflows.runtime import WorkflowRuntime
    from workflows.types import WorkflowContext, WorkflowActionResult

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ENHANCE_MODEL = "deepseek-v4-pro"
DEFAULT_REVIEW_MODEL = "deepseek-v4-flash"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    apply_runtime_env(args)
    event_logger = build_event_logger(args)

    try:
        runtime = WorkflowRuntime()

        if args.command == "status":
            status = runtime.get_status(
                "rtl_manual",
                {"project_root": args.project_root, "top_module": args.top_module},
                WorkflowContext(event_logger=event_logger),
            )
            print_status_summary(status)
            return 0 if status.ok else 1

        if args.command == "build":
            result = runtime.run_action(
                "rtl_manual",
                "build",
                {
                    "project_root": args.project_root,
                    "rtl_inputs": args.rtl_inputs,
                    "top_module": args.top_module,
                    "audience": args.audience,
                    "evidence_mode": args.evidence_mode,
                    "enrich_modules": args.enrich_modules,
                    "force": args.force,
                },
                WorkflowContext(event_logger=event_logger),
            )
            if not result.ok:
                print_result_error(result)
                return 1
            print_build_summary(result)
            return 0

        if args.command == "source-review":
            client, model = build_model_client(args)
            result = runtime.run_action(
                "rtl_manual",
                "source_review",
                {"project_root": args.project_root, "top_module": args.top_module, "model": model},
                WorkflowContext(event_logger=event_logger, model_client=client, model=model),
            )
            if not result.ok:
                print_result_error(result)
                return 1
            print_source_review_summary(result)
            return 0

        if args.command == "enhance":
            client, model = build_model_client(args)
            if client is None or model is None:
                print("error: enhance requires a model client; set an API key or pass --require-llm", file=sys.stderr)
                return 2
            if args.main_manual:
                result = runtime.run_action(
                    "rtl_manual",
                    "enhance_main",
                    {"project_root": args.project_root, "top_module": args.top_module, "model": model},
                    WorkflowContext(event_logger=event_logger, model_client=client, model=model),
                )
            elif args.all_modules or args.modules:
                result = runtime.run_action(
                    "rtl_manual",
                    "enhance_modules",
                    {
                        "project_root": args.project_root,
                        "top_module": args.top_module,
                        "target_modules": args.modules,
                        "module_filter": args.module_filter,
                        "model": model,
                    },
                    WorkflowContext(event_logger=event_logger, model_client=client, model=model),
                )
            else:
                result = runtime.run_action(
                    "rtl_manual",
                    "enhance_module",
                    {
                        "project_root": args.project_root,
                        "top_module": args.top_module,
                        "target_module": args.target_module,
                        "model": model,
                    },
                    WorkflowContext(event_logger=event_logger, model_client=client, model=model),
                )
            if not result.ok:
                print_result_error(result)
                if result.action == "enhance_modules":
                    print_enhance_summary(result)
                return 1
            print_enhance_summary(result)
            return 0

        if args.command == "compose":
            compose_result = runtime.run_action(
                "rtl_manual",
                "compose",
                {"project_root": args.project_root, "top_module": args.top_module},
                WorkflowContext(event_logger=event_logger),
            )
            if not compose_result.ok:
                print_result_error(compose_result)
                return 1
            review_client, review_model = build_model_client(args)
            review_result = runtime.run_action(
                "rtl_manual",
                "review",
                {"project_root": args.project_root, "top_module": args.top_module, "model": review_model},
                WorkflowContext(event_logger=event_logger, model_client=review_client, model=review_model),
            )
            if not review_result.ok:
                print_result_error(review_result)
                return 1
            print_compose_summary(compose_result, review_result)
            return 0

        if args.command == "review":
            client, model = build_model_client(args)
            result = runtime.run_action(
                "rtl_manual",
                "review",
                {"project_root": args.project_root, "top_module": args.top_module, "model": model},
                WorkflowContext(event_logger=event_logger, model_client=client, model=model),
            )
            if not result.ok:
                print_result_error(result)
                return 1
            print_review_summary(result)
            return 0

        print(f"error: unknown command {args.command!r}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.manual_cli",
        description="Run the layered RTL manual workflow.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Read manifest and artifact status.")
    add_project_args(status)
    add_log_args(status)

    build = subparsers.add_parser("build", help="Generate deterministic base manual artifacts.")
    add_project_args(build, include_rtl_inputs=True)
    build.add_argument("--audience", choices=("newcomer", "maintainer", "reviewer"), default="newcomer")
    build.add_argument(
        "--evidence-mode",
        choices=(PROJECT_EVIDENCE_MODE, READING_PATH_EVIDENCE_MODE),
        default=PROJECT_EVIDENCE_MODE,
    )
    build.add_argument("--enrich-modules", default="", help="Comma-separated Semantic Layer module allowlist.")
    build.add_argument("--force", action="store_true", help="Regenerate parser/knowledge/base artifacts.")
    add_runtime_args(build)
    add_log_args(build)

    source_review = subparsers.add_parser("source-review", help="Run controlled source review and mark enhanced fragments stale.")
    add_project_args(source_review)
    add_model_args(source_review)
    add_log_args(source_review)

    enhance = subparsers.add_parser("enhance", help="Enhance one base target into a separate fragment.")
    add_project_args(enhance)
    target = enhance.add_mutually_exclusive_group(required=True)
    target.add_argument("--main-manual", action="store_true", help="Enhance the whole base main manual.")
    target.add_argument("--target-module", default="", help="Enhance exactly one base module page.")
    target.add_argument("--all-modules", action="store_true", help="Enhance module pages selected by --module-filter.")
    target.add_argument("--modules", default="", help="Comma-separated module page names to enhance.")
    enhance.add_argument(
        "--module-filter",
        choices=("all", "pending", "missing", "stale", "failed", "invalid", "success", "retryable", "not-success"),
        default="all",
        help="Filter used with --all-modules. retryable means pending/missing/stale/failed/invalid.",
    )
    add_model_args(enhance)
    add_log_args(enhance)

    compose = subparsers.add_parser("compose", help="Compose final manual from base plus valid enhanced fragments.")
    add_project_args(compose)
    add_model_args(compose)
    add_log_args(compose)

    review = subparsers.add_parser("review", help="Review the composed final manual and module pages.")
    add_project_args(review)
    add_model_args(review)
    add_log_args(review)
    return parser


def add_project_args(parser: argparse.ArgumentParser, *, include_rtl_inputs: bool = False) -> None:
    parser.add_argument("--project-root", default=str(BASE_DIR / "rtl"), help="RTL project root. Defaults to this repo's rtl sample root.")
    if include_rtl_inputs:
        parser.add_argument("--rtl-inputs", default="rtl", help="RTL input directory under project root.")
    parser.add_argument("--top-module", required=True, help="Top module name, for example arm_soc_top.")


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--parser-timeout", type=int, default=0, help="Parser tool timeout in seconds.")
    parser.add_argument("--knowledge-timeout", type=int, default=0, help="Knowledge pipeline timeout in seconds.")


def add_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        default="",
        help=(
            "OpenAI-compatible model. Defaults to deepseek-v4-flash for source-review/review/compose review, "
            "and deepseek-v4-pro for enhance unless overridden by environment."
        ),
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
        help="Disable model calls. For source-review this records evidence gaps; enhance will fail.",
    )
    parser.add_argument("--require-llm", action="store_true", help="Fail fast if no model client can be created.")


def add_log_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--log-events", action="store_true", help="Write CLI workflow events to data/logs.")


def _load_dotenv() -> None:
    try:
        import dotenv
    except ImportError:
        return
    dotenv.load_dotenv(BASE_DIR / ".env")
    dotenv.load_dotenv()


def apply_runtime_env(args: argparse.Namespace) -> None:
    if getattr(args, "parser_timeout", 0) and args.parser_timeout > 0:
        os.environ["RTL_MANUAL_PARSER_TIMEOUT"] = str(args.parser_timeout)
    if getattr(args, "knowledge_timeout", 0) and args.knowledge_timeout > 0:
        os.environ["RTL_MANUAL_KNOWLEDGE_TIMEOUT"] = str(args.knowledge_timeout)
        os.environ.setdefault("RTL_MANUAL_KNOWLEDGE_WRAPPER_TIMEOUT", str(args.knowledge_timeout + 120))


def build_model_client(args: argparse.Namespace):
    model = _select_model(args)
    if getattr(args, "no_llm", False):
        if getattr(args, "require_llm", False):
            raise RuntimeError("--no-llm cannot be combined with --require-llm")
        return None, None

    api_key = getattr(args, "api_key", "") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY")
    base_url = (
        getattr(args, "base_url", "")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or "https://api.deepseek.com"
    )
    if not api_key:
        if getattr(args, "require_llm", False):
            raise RuntimeError("missing API key; set OPENAI_API_KEY, DEEPSEEK_API_KEY, LLM_API_KEY, or pass --api-key")
        print("warning: no API key found; model-backed steps will use fallback behavior.", file=sys.stderr)
        return None, None

    try:
        from openai import OpenAI
    except ImportError as exc:
        if getattr(args, "require_llm", False):
            raise RuntimeError("openai package is required for model-backed workflow steps") from exc
        print("warning: openai package is missing; model-backed steps will use fallback behavior.", file=sys.stderr)
        return None, None

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs), model


def _select_model(args: argparse.Namespace) -> str:
    explicit = getattr(args, "model", "")
    if explicit:
        return explicit
    command = getattr(args, "command", "")
    if command == "source-review":
        return (
            os.getenv("MANUAL_SOURCE_REVIEW_MODEL")
            or os.getenv("MANUAL_REVIEW_MODEL")
            or os.getenv("DEEPSEEK_REVIEW_MODEL")
            or os.getenv("OPENAI_REVIEW_MODEL")
            or DEFAULT_REVIEW_MODEL
        )
    if command in {"review", "compose"}:
        return (
            os.getenv("MANUAL_REVIEW_MODEL")
            or os.getenv("DEEPSEEK_REVIEW_MODEL")
            or os.getenv("OPENAI_REVIEW_MODEL")
            or DEFAULT_REVIEW_MODEL
        )
    return (
        os.getenv("MANUAL_ENHANCE_MODEL")
        or os.getenv("DEEPSEEK_MODEL")
        or os.getenv("MANUAL_WORKFLOW_MODEL")
        or os.getenv("MANUAL_IR_ENRICH_MODEL")
        or os.getenv("OPENAI_MODEL")
        or DEFAULT_ENHANCE_MODEL
    )


def build_event_logger(args: argparse.Namespace):
    if not getattr(args, "log_events", False):
        return None
    run_id = f"manual_cli_{args.command}_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    return lambda event_type, **payload: log_event(run_id, event_type, **payload)


def print_status_summary(result) -> None:
    payload = asdict(result)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def print_result_error(result: WorkflowActionResult) -> None:
    message = result.message or "; ".join(result.errors) or "workflow action failed"
    print(f"error: {message}", file=sys.stderr)


def print_build_summary(result: WorkflowActionResult | dict[str, Any]) -> None:
    print("Base manual built")
    artifacts = result.artifacts if isinstance(result, WorkflowActionResult) else result
    print(f"- base_main: {artifacts.get('base_main')}")
    print(f"- base_modules: {artifacts.get('base_modules_dir')}")
    print(f"- manifest: {artifacts.get('manifest') or artifacts.get('manifest_path')}")


def print_source_review_summary(result: WorkflowActionResult | dict[str, Any]) -> None:
    print("Source review complete")
    artifacts = result.artifacts if isinstance(result, WorkflowActionResult) else result
    print(f"- source_review: {artifacts.get('source_review') or artifacts.get('source_review_output_path') or 'not written'}")
    print("- manifest: marked enhanced fragments stale; rerun enhance and compose")


def print_enhance_summary(result: WorkflowActionResult | dict[str, Any]) -> None:
    print("Enhancement complete")
    artifacts = result.artifacts if isinstance(result, WorkflowActionResult) else result
    status = result.status if isinstance(result, WorkflowActionResult) else {}
    if "target_count" in status:
        print(f"- target_count: {status.get('target_count')}")
        print(f"- success_count: {status.get('success_count')}")
        print(f"- failed_count: {status.get('failed_count')}")
        failures = [item for item in status.get("results", []) if item.get("status") == "failed"]
        if failures:
            print("- failures:")
            for item in failures:
                print(f"  - {item.get('module')}: {item.get('error')}")
        print(f"- manifest: {artifacts.get('manifest') or artifacts.get('manifest_path')}")
        return
    print(f"- enhanced: {artifacts.get('enhanced') or artifacts.get('enhanced_path')}")
    print(f"- manifest: {artifacts.get('manifest') or artifacts.get('manifest_path')}")


def print_compose_summary(compose_result: WorkflowActionResult | dict[str, Any], review_result: WorkflowActionResult | dict[str, Any]) -> None:
    print("Final manual composed")
    artifacts = compose_result.artifacts if isinstance(compose_result, WorkflowActionResult) else compose_result
    status = compose_result.status if isinstance(compose_result, WorkflowActionResult) else compose_result
    review_artifacts = review_result.artifacts if isinstance(review_result, WorkflowActionResult) else review_result
    print(f"- final_main: {artifacts.get('final_main')}")
    print(f"- final_modules: {artifacts.get('final_modules_dir')}")
    print(f"- review: {review_artifacts.get('review') or review_artifacts.get('review_output_path') or 'not written'}")
    print(f"- enhanced_count: {status.get('enhanced_count')}")
    print(f"- fallback_count: {status.get('fallback_count')}")
    print(f"- stale_count: {status.get('stale_count')}")
    print(f"- invalid_count: {status.get('invalid_count')}")
    print(f"- manifest: {artifacts.get('manifest') or artifacts.get('manifest_path')}")


def print_review_summary(result: WorkflowActionResult | dict[str, Any]) -> None:
    print("Final manual reviewed")
    artifacts = result.artifacts if isinstance(result, WorkflowActionResult) else result
    print(f"- review: {artifacts.get('review') or artifacts.get('review_output_path') or 'not written'}")
    print(f"- manifest: {artifacts.get('manifest') or artifacts.get('manifest_path')}")


if __name__ == "__main__":
    raise SystemExit(main())
