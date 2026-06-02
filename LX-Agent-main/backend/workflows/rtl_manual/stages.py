from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def build_state(
    *,
    project_root: str | Path,
    rtl_inputs: str = "rtl",
    top_module: str,
    audience: str = "newcomer",
    evidence_mode: str = "project",
    enrich_modules: str = "",
    force_stages: list[str] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    state = legacy._ensure_state({
        "active": True,
        "project_root": str(Path(project_root).expanduser().resolve()),
        "rtl_inputs": rtl_inputs,
        "top_module": top_module,
        "audience": audience,
        "evidence_mode": evidence_mode,
        "semantic_enrichment": True,
        "enrich_modules": enrich_modules,
        "force_stages": list(force_stages or []),
        "auto_run": False,
    })
    parser_dir = legacy._select_parser_dir(state["project_root"])
    legacy._refresh_artifact_paths(state, parser_dir)
    return state


def run_pre_base_stages(
    state: dict[str, Any],
    *,
    base_dir: str | Path,
    event_logger: Callable[..., None] | None = None,
) -> list[dict[str, Any]]:
    from ... import manual_workflow as legacy

    sequence = [
        ("references", lambda: legacy._run_reference_stage(state, Path(base_dir), event_logger)),
        ("parser", lambda: legacy._run_parser_stage(state, event_logger)),
        ("knowledge", lambda: legacy._run_knowledge_stage(state, event_logger)),
        ("evidence", lambda: legacy._run_evidence_stage(state, event_logger)),
        ("outline", lambda: legacy._run_outline_stage(state, event_logger)),
        ("chapter_plan", lambda: legacy._run_chapter_plan_stage(state, event_logger)),
    ]
    results = []
    for stage, runner in sequence:
        state["stage"] = stage
        reply = runner()
        results.append({
            "stage": stage,
            "reply": reply,
            "status": "failed" if state.get("last_error") else "done",
            "next_stage": state.get("stage", ""),
        })
        if state.get("last_error"):
            break
    return results

