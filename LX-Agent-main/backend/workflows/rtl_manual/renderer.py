from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .artifacts import load_manifest, manual_paths, refresh_base_manifest, save_manifest


def render_base_manual(
    state: dict[str, Any],
    *,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    missing = legacy._ensure_manual_stage_inputs(state, event_logger)
    if missing:
        raise RuntimeError(missing)

    top_module = state["top_module"]
    paths = manual_paths(state["project_root"], top_module)
    paths["base_main"].parent.mkdir(parents=True, exist_ok=True)
    state["_manual_output_stem"] = paths["base_main"].stem
    state["manual_llm_page_status"] = {}

    _log(event_logger, "manual_base_render_start", top_module=top_module, output_path=str(paths["base_main"]))
    manual = legacy._render_manual_context_markdown(state)
    paths["base_main"].write_text(manual + "\n", encoding="utf-8")
    module_page_paths = legacy._write_module_pages(state, paths["base_main"], client=None, model=None)

    state["base_manual_output_path"] = str(paths["base_main"])
    state["base_manual_module_pages_dir"] = str(paths["base_modules_dir"])
    state["base_manual_module_page_count"] = len(module_page_paths)

    manifest = load_manifest(state["project_root"], top_module)
    manifest = refresh_base_manifest(state["project_root"], top_module, manifest)
    manifest_path = save_manifest(state["project_root"], top_module, manifest)

    _log(
        event_logger,
        "manual_base_render_end",
        top_module=top_module,
        status="success",
        output_path=str(paths["base_main"]),
        module_pages_dir=str(paths["base_modules_dir"]),
        module_page_count=len(module_page_paths),
        manifest_path=str(manifest_path),
    )
    return {
        "manual": manual,
        "base_main": paths["base_main"],
        "base_modules_dir": paths["base_modules_dir"],
        "module_page_paths": module_page_paths,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }


def _log(event_logger: Callable[..., None] | None, event_type: str, **payload: Any) -> None:
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass
