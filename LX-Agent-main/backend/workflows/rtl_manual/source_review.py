from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .artifacts import mark_source_review_invalidated
from .stages import build_state


def run_source_review(
    *,
    project_root: str | Path,
    top_module: str,
    client: Any,
    model: str | None,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    state = build_state(project_root=project_root, top_module=top_module, force_stages=["source_review"])
    state["stage"] = "source_review"
    _log(event_logger, "manual_source_review_start", top_module=top_module)
    reply = legacy._run_source_review_stage(state, client, model, event_logger)
    if state.get("last_error"):
        _log(event_logger, "manual_source_review_end", top_module=top_module, status="failed", error=state["last_error"])
        raise RuntimeError(state["last_error"])
    manifest = mark_source_review_invalidated(project_root, top_module)
    _log(
        event_logger,
        "manual_source_review_end",
        top_module=top_module,
        status="success",
        output_path=state.get("source_review_output_path", ""),
    )
    return {
        "state": state,
        "reply": reply,
        "source_review_output_path": state.get("source_review_output_path", ""),
        "manifest": manifest,
    }


def _log(event_logger: Callable[..., None] | None, event_type: str, **payload: Any) -> None:
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass

