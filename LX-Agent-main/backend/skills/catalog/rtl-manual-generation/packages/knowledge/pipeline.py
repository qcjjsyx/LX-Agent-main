"""Run the Knowledge IR documentation pipeline from parser artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, Iterable, List

try:
    from .ai_context import build_ai_context
    from .knowledge_ir import build_knowledge_ir
    from .llm_client import OpenAICompatibleLLMClient
    from .manual_context import build_manual_context
    from .semantic_layer import enrich_semantic_layer
except ImportError:  # pragma: no cover - supports direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ai_context import build_ai_context
    from knowledge_ir import build_knowledge_ir
    from llm_client import OpenAICompatibleLLMClient
    from manual_context import build_manual_context
    from semantic_layer import enrich_semantic_layer


SCHEMA_VERSION = "0.1"


def run_knowledge_pipeline(
    parser_artifacts_root: str | Path,
    top_module: str,
    *,
    knowledge_output_root: str | Path = "rtl/knowledge_ir",
    manual_context_output_root: str | Path = "rtl/manual_context",
    clean: bool = True,
    semantic_modules: Iterable[str] | None = None,
    include_flows: bool = True,
    max_flows_per_module: int | None = None,
    semantic_workers: int | None = None,
    skip_failed_semantic: bool = False,
    skip_semantic: bool = False,
    semantic_dry_run: bool = False,
    semantic_model: str | None = None,
    semantic_base_url: str | None = None,
    semantic_api_key: str | None = None,
    reuse_semantic_cache: bool = True,
) -> Dict[str, Any]:
    """Run Knowledge IR, AI Context, Semantic Layer, and Manual Context."""

    parser_root = Path(parser_artifacts_root)
    if not parser_root.exists():
        raise FileNotFoundError(f"parser artifacts root does not exist: {parser_root}")
    if not top_module.strip():
        raise ValueError("top_module is required")

    knowledge_root = Path(knowledge_output_root) / top_module
    manual_context_root = Path(manual_context_output_root) / top_module
    steps: List[Dict[str, Any]] = []
    semantic_cache_root = preserve_semantic_cache(
        knowledge_root,
        enabled=clean and reuse_semantic_cache and not skip_semantic and not semantic_dry_run,
    )

    knowledge_manifest = build_knowledge_ir(
        parser_root,
        top_module,
        knowledge_root,
        clean=clean,
    )
    steps.append(
        {
            "name": "knowledge_ir",
            "status": "passed",
            "output_dir": str(knowledge_root),
            "counts": knowledge_manifest.get("counts", {}),
        }
    )

    ai_index = build_ai_context(
        knowledge_root,
        parser_root,
        clean=clean,
    )
    steps.append(
        {
            "name": "ai_context",
            "status": "passed",
            "output_dir": str(knowledge_root / "ai_context"),
            "counts": ai_index.get("counts", {}),
        }
    )

    restore_semantic_cache(knowledge_root, semantic_cache_root)
    semantic_report: Dict[str, Any] = {}
    if skip_semantic:
        semantic_report = {
            "schema": "knowledge_ir_semantic_report",
            "schema_version": "",
            "top_module": top_module,
            "status": "skipped",
            "issues": [
                {
                    "level": "warning",
                    "code": "semantic_skipped",
                    "message": "Semantic Layer was skipped by command-line option.",
                }
            ],
        }
    else:
        client = None
        if not semantic_dry_run:
            client = OpenAICompatibleLLMClient(
                model=semantic_model,
                api_key=semantic_api_key,
                base_url=semantic_base_url,
            )
        semantic_report = enrich_semantic_layer(
            knowledge_root,
            modules=semantic_modules,
            include_flows=include_flows,
            max_flows_per_module=max_flows_per_module,
            max_workers=semantic_workers,
            llm_client=client,
            skip_failed=skip_failed_semantic,
            dry_run=semantic_dry_run,
        )
    steps.append(
        {
            "name": "semantic_layer",
            "status": semantic_report.get("status", "unknown"),
            "output_dir": str(knowledge_root / "semantic"),
            "counts": semantic_report.get("count", semantic_report.get("counts", {})),
            "claim_types": semantic_report.get("claim_types", {}),
            "issues": semantic_report.get("issues", []),
        }
    )

    manual_manifest = build_manual_context(
        knowledge_root,
        parser_root,
        manual_context_root,
        clean=clean,
        include_semantic=not skip_semantic and not semantic_dry_run,
    )
    steps.append(
        {
            "name": "manual_context",
            "status": "passed" if manual_manifest.get("counts", {}).get("validation_issues", 0) == 0 else "passed_with_validation_issues",
            "output_dir": str(manual_context_root),
            "counts": manual_manifest.get("counts", {}),
        }
    )

    status = "passed"
    if skip_semantic or semantic_dry_run:
        status = "passed_without_semantic"
    if any(step.get("status") in {"failed", "error"} for step in steps):
        status = "failed"

    return {
        "schema": "knowledge_pipeline_report",
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "top_module": top_module,
        "inputs": {
            "parser_artifacts_root": str(parser_root),
        },
        "outputs": {
            "knowledge_dir": str(knowledge_root),
            "ai_context_dir": str(knowledge_root / "ai_context"),
            "semantic_dir": str(knowledge_root / "semantic"),
            "manual_context_dir": str(manual_context_root),
        },
        "steps": steps,
    }


def preserve_semantic_cache(knowledge_root: Path, *, enabled: bool) -> Path | None:
    semantic_root = knowledge_root / "semantic"
    if not enabled or not semantic_root.exists():
        return None
    cache_root = Path(tempfile.mkdtemp(prefix=f"{knowledge_root.name}_semantic_", dir=str(knowledge_root.parent)))
    shutil.copytree(semantic_root, cache_root / "semantic")
    return cache_root


def restore_semantic_cache(knowledge_root: Path, cache_root: Path | None) -> None:
    if cache_root is None:
        return
    cached_semantic_root = cache_root / "semantic"
    semantic_root = knowledge_root / "semantic"
    try:
        if cached_semantic_root.exists():
            if semantic_root.exists():
                shutil.rmtree(semantic_root)
            shutil.copytree(cached_semantic_root, semantic_root)
    finally:
        shutil.rmtree(cache_root, ignore_errors=True)


def parse_modules_arg(value: str) -> List[str] | None:
    if not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Knowledge IR, AI Context, Semantic Layer, and Manual Context "
            "from parser pipeline artifacts."
        )
    )
    parser.add_argument("--artifacts-root", default="rtl/parser_pipeline_rtl")
    parser.add_argument("--top-module", default="arm_soc_top")
    parser.add_argument("--knowledge-output-root", default="rtl/knowledge_ir")
    parser.add_argument("--manual-context-output-root", default="rtl/manual_context")
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--semantic-modules", default="", help="Comma-separated modules for Semantic Layer. Defaults to all modules.")
    parser.add_argument("--no-flows", action="store_true", help="Do not generate Semantic Layer flow claims.")
    parser.add_argument("--max-flows-per-module", type=int, default=None)
    parser.add_argument("--semantic-workers", type=int, default=None, help="Parallel Semantic Layer LLM workers. Defaults to RTL_MANUAL_SEMANTIC_WORKERS or 4.")
    parser.add_argument("--skip-failed-semantic", action="store_true")
    parser.add_argument("--skip-semantic", action="store_true", help="Debug option: skip Semantic Layer and build Manual Context without AI claims.")
    parser.add_argument("--semantic-dry-run", action="store_true", help="Plan Semantic Layer only; no semantic files are written.")
    parser.add_argument("--semantic-model", default=None)
    parser.add_argument("--semantic-base-url", default=None)
    parser.add_argument("--semantic-api-key", default=None)
    parser.add_argument("--no-semantic-cache", action="store_true", help="Do not preserve existing Semantic Layer cards during a clean run.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = run_knowledge_pipeline(
        args.artifacts_root,
        args.top_module,
        knowledge_output_root=args.knowledge_output_root,
        manual_context_output_root=args.manual_context_output_root,
        clean=not args.no_clean,
        semantic_modules=parse_modules_arg(args.semantic_modules),
        include_flows=not args.no_flows,
        max_flows_per_module=args.max_flows_per_module,
        semantic_workers=args.semantic_workers,
        skip_failed_semantic=args.skip_failed_semantic,
        skip_semantic=args.skip_semantic,
        semantic_dry_run=args.semantic_dry_run,
        semantic_model=args.semantic_model,
        semantic_base_url=args.semantic_base_url,
        semantic_api_key=args.semantic_api_key,
        reuse_semantic_cache=not args.no_semantic_cache,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {"passed", "passed_without_semantic"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
