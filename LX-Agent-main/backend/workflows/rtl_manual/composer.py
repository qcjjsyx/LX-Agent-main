from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from .artifacts import (
    enhancement_entry,
    load_manifest,
    manual_paths,
    resolve_manifest_path,
    save_manifest,
    sha256_file,
    update_compose_status,
)


## 组合最终手册
def compose_final_manual(
    *,
    project_root: str | Path,
    top_module: str,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    paths = manual_paths(project_root, top_module)
    manifest = load_manifest(project_root, top_module)
    if not paths["base_main"].exists():
        raise FileNotFoundError(f"base main manual not found: {paths['base_main']}")

    _log(event_logger, "manual_compose_start", top_module=top_module)
    paths["final_main"].parent.mkdir(parents=True, exist_ok=True)
    paths["final_modules_dir"].mkdir(parents=True, exist_ok=True)
    for old_page in paths["final_modules_dir"].glob("*.md"):
        old_page.unlink()

    enhanced_count = 0
    fallback_count = 0
    stale_count = 0
    invalid_count = 0

    main_text, main_status = _select_main_text(paths, manifest)
    if main_status == "enhanced":
        enhanced_count += 1
    elif main_status == "stale":
        stale_count += 1
        fallback_count += 1
    elif main_status == "invalid":
        invalid_count += 1
        fallback_count += 1
    else:
        fallback_count += 1
    paths["final_main"].write_text(_rewrite_main_links(main_text, top_module).rstrip() + "\n", encoding="utf-8")

    base_pages = sorted(paths["base_modules_dir"].glob("*.md")) if paths["base_modules_dir"].exists() else []
    for base_page in base_pages:
        module_name = base_page.stem
        chosen_path, status = _select_module_page(project_root, manifest, module_name, base_page)
        shutil.copyfile(chosen_path, paths["final_modules_dir"] / base_page.name)
        if status == "enhanced":
            enhanced_count += 1
        elif status == "stale":
            stale_count += 1
            fallback_count += 1
        elif status == "invalid":
            invalid_count += 1
            fallback_count += 1
        else:
            fallback_count += 1

    manifest = update_compose_status(
        project_root,
        top_module,
        manifest,
        enhanced_count=enhanced_count,
        fallback_count=fallback_count,
        stale_count=stale_count,
        invalid_count=invalid_count,
    )
    manifest_path = save_manifest(project_root, top_module, manifest)
    _log(
        event_logger,
        "manual_compose_end",
        top_module=top_module,
        status="success",
        final_main=str(paths["final_main"]),
        final_modules_dir=str(paths["final_modules_dir"]),
        enhanced_count=enhanced_count,
        fallback_count=fallback_count,
        stale_count=stale_count,
        invalid_count=invalid_count,
        manifest_path=str(manifest_path),
    )
    return {
        "final_main": paths["final_main"],
        "final_modules_dir": paths["final_modules_dir"],
        "manifest_path": manifest_path,
        "enhanced_count": enhanced_count,
        "fallback_count": fallback_count,
        "stale_count": stale_count,
        "invalid_count": invalid_count,
    }


def _select_main_text(paths: dict[str, Path], manifest: dict[str, Any]) -> tuple[str, str]:
    entry = enhancement_entry(manifest, "main", "main")
    base_hash = sha256_file(paths["base_main"])
    if entry.get("status") != "success":
        return paths["base_main"].read_text(encoding="utf-8"), "fallback"
    if entry.get("base_hash") != base_hash:
        entry["status"] = "stale"
        entry["error"] = "Base main manual changed."
        return paths["base_main"].read_text(encoding="utf-8"), "stale"
    enhanced_path = resolve_manifest_path(paths["project_root"], entry.get("enhanced_path", ""))
    if not enhanced_path.exists():
        entry["status"] = "invalid"
        entry["error"] = "Enhanced main manual is missing."
        return paths["base_main"].read_text(encoding="utf-8"), "invalid"
    return enhanced_path.read_text(encoding="utf-8"), "enhanced"


def _select_module_page(
    project_root: str | Path,
    manifest: dict[str, Any],
    module_name: str,
    base_page: Path,
) -> tuple[Path, str]:
    entry = enhancement_entry(manifest, "module", module_name)
    if entry.get("status") != "success":
        return base_page, "fallback"
    if entry.get("base_hash") != sha256_file(base_page):
        entry["status"] = "stale"
        entry["error"] = "Base module page changed."
        return base_page, "stale"
    enhanced_path = resolve_manifest_path(project_root, entry.get("enhanced_path", ""))
    if not enhanced_path.exists():
        entry["status"] = "invalid"
        entry["error"] = "Enhanced module page is missing."
        return base_page, "invalid"
    return enhanced_path, "enhanced"


def _rewrite_main_links(markdown: str, top_module: str) -> str:
    return (
        markdown.replace(f"{top_module}_base_modules/", f"{top_module}_generated_modules/")
        .replace(f"{top_module}_enhanced/modules/", f"{top_module}_generated_modules/")
    )


def _log(event_logger: Callable[..., None] | None, event_type: str, **payload: Any) -> None:
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass

