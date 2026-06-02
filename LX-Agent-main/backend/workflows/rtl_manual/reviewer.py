from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .artifacts import manual_paths
from .stages import build_state


def review_final_manual(
    *,
    project_root: str | Path,
    top_module: str,
    client: Any = None,
    model: str | None = None,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    paths = manual_paths(project_root, top_module)
    state = build_state(project_root=project_root, top_module=top_module, force_stages=["review"])
    state["stage"] = "review"
    state["manual_output_path"] = str(paths["final_main"])
    state["manual_module_pages_dir"] = str(paths["final_modules_dir"])
    reply = legacy._run_review_stage(state, client, model, event_logger)
    if state.get("last_error"):
        raise RuntimeError(state["last_error"])
    return {
        "state": state,
        "reply": reply,
        "review_output_path": state.get("review_output_path", ""),
    }

