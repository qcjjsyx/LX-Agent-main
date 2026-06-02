from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .composer import compose_final_manual
from .enhancer import enhance_main_manual, enhance_module_page
from .renderer import render_base_manual
from .reviewer import review_final_manual
from .source_review import run_source_review
from .stages import build_state, run_pre_base_stages


BASE_DIR = Path(__file__).resolve().parents[3]


def build_base_manual(
    *,
    project_root: str | Path,
    rtl_inputs: str = "rtl",
    top_module: str,
    audience: str = "newcomer",
    evidence_mode: str = "project",
    enrich_modules: str = "",
    force: bool = False,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    force_stages = ["references", "parser", "knowledge", "evidence", "outline", "chapter_plan"] if force else []
    state = build_state(
        project_root=project_root,
        rtl_inputs=rtl_inputs,
        top_module=top_module,
        audience=audience,
        evidence_mode=evidence_mode,
        enrich_modules=enrich_modules,
        force_stages=force_stages,
    )
    stage_results = run_pre_base_stages(state, base_dir=BASE_DIR, event_logger=event_logger)
    if state.get("last_error"):
        raise RuntimeError(state["last_error"])
    base_result = render_base_manual(state, event_logger=event_logger)
    return {
        "state": state,
        "stage_results": stage_results,
        **base_result,
    }


__all__ = [
    "build_base_manual",
    "compose_final_manual",
    "enhance_main_manual",
    "enhance_module_page",
    "run_source_review",
    "review_final_manual",
]

