from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .artifacts import (
    base_target_entry,
    enhancement_entry,
    load_manifest,
    manual_paths,
    record_enhancement,
    resolve_manifest_path,
    save_manifest,
    sha256_file,
)
from .stages import build_state


def enhance_main_manual(
    *,
    project_root: str | Path,
    top_module: str,
    client: Any,
    model: str,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    paths = manual_paths(project_root, top_module)
    manifest = load_manifest(project_root, top_module)
    base_entry = base_target_entry(manifest, "main", "main")
    base_path = paths["base_main"]
    if not base_path.exists():
        raise FileNotFoundError(f"base main manual not found: {base_path}")
    base_hash = sha256_file(base_path)
    if base_entry.get("hash") and base_entry.get("hash") != base_hash:
        raise RuntimeError("base main hash differs from manifest; run build first")

    draft = base_path.read_text(encoding="utf-8")
    state = build_state(project_root=project_root, top_module=top_module)
    state["manual_llm_required"] = True
    try:
        digest = legacy._load_manual_context_digest(state)
        manual_context_packet = legacy._build_main_manual_polish_packet(state, digest, draft)
    except Exception as exc:
        digest = {}
        manual_context_packet = {
            "top_module": top_module,
            "manual_context_available": False,
            "load_error": str(exc),
            "evidence_boundary": [
                "Manual Context digest could not be loaded; only the deterministic draft may be polished.",
            ],
        }
    _log(event_logger, "manual_enhancement_target_start", target_type="main", target_name="main", model=model)
    try:
        enhanced = legacy._polish_manual_with_llm(state, draft, client, model, manual_context_packet)
        valid, reason = legacy._validate_polished_manual(draft, enhanced, {"top_module": top_module, "evidence_digest": digest})
        if not valid:
            raise ValueError(reason)
        paths["enhanced_main"].parent.mkdir(parents=True, exist_ok=True)
        paths["enhanced_main"].write_text(enhanced.strip() + "\n", encoding="utf-8")
        manifest = record_enhancement(
            project_root,
            top_module,
            manifest,
            target_type="main",
            target_name="main",
            status="success",
            base_hash=base_hash,
            enhanced_path=paths["enhanced_main"],
            model=model,
        )
        status = "success"
        error = ""
    except Exception as exc:
        manifest = record_enhancement(
            project_root,
            top_module,
            manifest,
            target_type="main",
            target_name="main",
            status="failed",
            base_hash=base_hash,
            enhanced_path=paths["enhanced_main"],
            model=model,
            error=str(exc),
        )
        status = "failed"
        error = str(exc)
    manifest_path = save_manifest(project_root, top_module, manifest)
    _log(
        event_logger,
        "manual_enhancement_target_end",
        target_type="main",
        target_name="main",
        status=status,
        error=error,
        enhanced_path=str(paths["enhanced_main"]),
        manifest_path=str(manifest_path),
    )
    if status != "success":
        raise RuntimeError(error)
    return {"status": status, "enhanced_path": paths["enhanced_main"], "manifest_path": manifest_path}


def enhance_module_page(
    *,
    project_root: str | Path,
    top_module: str,
    target_module: str,
    client: Any,
    model: str,
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    from ... import manual_workflow as legacy

    paths = manual_paths(project_root, top_module)
    manifest = load_manifest(project_root, top_module)
    base_entry = base_target_entry(manifest, "module", target_module)
    base_path = paths["base_modules_dir"] / f"{legacy.safe_filename(target_module)}.md"
    if not base_path.exists():
        raise FileNotFoundError(f"base module page not found: {base_path}")
    base_hash = sha256_file(base_path)
    if base_entry.get("hash") and base_entry.get("hash") != base_hash:
        raise RuntimeError("base module page hash differs from manifest; run build first")

    draft = base_path.read_text(encoding="utf-8")
    state = build_state(project_root=project_root, top_module=top_module)
    digest = legacy._load_manual_context_digest(state)
    module = next((item for item in digest.get("modules", []) if item.get("module_name") == target_module), None)
    if not module:
        raise ValueError(f"module not found in Manual Context: {target_module}")
    packet = legacy._build_module_page_polish_packet(state, digest, module, draft)
    enhanced_path = paths["enhanced_modules_dir"] / f"{legacy.safe_filename(target_module)}.md"

    _log(event_logger, "manual_enhancement_target_start", target_type="module", target_name=target_module, model=model)
    try:
        enhanced = legacy._polish_module_page_with_llm(state, target_module, draft, packet, client, model)
        valid, reason = legacy._validate_polished_module_page(packet, draft, enhanced)
        if not valid:
            raise ValueError(reason)
        enhanced_path.parent.mkdir(parents=True, exist_ok=True)
        enhanced_path.write_text(enhanced.strip() + "\n", encoding="utf-8")
        manifest = record_enhancement(
            project_root,
            top_module,
            manifest,
            target_type="module",
            target_name=target_module,
            status="success",
            base_hash=base_hash,
            enhanced_path=enhanced_path,
            model=model,
        )
        status = "success"
        error = ""
    except Exception as exc:
        manifest = record_enhancement(
            project_root,
            top_module,
            manifest,
            target_type="module",
            target_name=target_module,
            status="failed",
            base_hash=base_hash,
            enhanced_path=enhanced_path,
            model=model,
            error=str(exc),
        )
        status = "failed"
        error = str(exc)
    manifest_path = save_manifest(project_root, top_module, manifest)
    _log(
        event_logger,
        "manual_enhancement_target_end",
        target_type="module",
        target_name=target_module,
        status=status,
        error=error,
        enhanced_path=str(enhanced_path),
        manifest_path=str(manifest_path),
    )
    if status != "success":
        raise RuntimeError(error)
    return {"status": status, "enhanced_path": enhanced_path, "manifest_path": manifest_path}


def enhance_module_pages_batch(
    *,
    project_root: str | Path,
    top_module: str,
    client: Any,
    model: str,
    target_modules: list[str] | str | None = None,
    module_filter: str = "all",
    event_logger: Callable[..., None] | None = None,
) -> dict[str, Any]:
    targets = select_module_enhancement_targets(
        project_root=project_root,
        top_module=top_module,
        target_modules=target_modules,
        module_filter=module_filter,
    )
    if not targets:
        raise ValueError(f"no module enhancement targets matched filter: {module_filter}")

    results = []
    success_count = 0
    failed_count = 0
    manifest_path = manual_paths(project_root, top_module)["manifest"]
    _log(
        event_logger,
        "manual_enhancement_batch_start",
        target_type="module",
        target_count=len(targets),
        module_filter=module_filter,
        model=model,
    )
    for module_name in targets:
        try:
            result = enhance_module_page(
                project_root=project_root,
                top_module=top_module,
                target_module=module_name,
                client=client,
                model=model,
                event_logger=event_logger,
            )
            success_count += 1
            manifest_path = result["manifest_path"]
            results.append({
                "module": module_name,
                "status": "success",
                "enhanced_path": str(result["enhanced_path"]),
                "error": "",
            })
        except Exception as exc:
            failed_count += 1
            results.append({
                "module": module_name,
                "status": "failed",
                "enhanced_path": "",
                "error": str(exc),
            })

    _log(
        event_logger,
        "manual_enhancement_batch_end",
        target_type="module",
        target_count=len(targets),
        success_count=success_count,
        failed_count=failed_count,
        manifest_path=str(manifest_path),
    )
    return {
        "status": "success" if failed_count == 0 else "partial_failed",
        "targets": targets,
        "results": results,
        "success_count": success_count,
        "failed_count": failed_count,
        "manifest_path": manifest_path,
    }


def select_module_enhancement_targets(
    *,
    project_root: str | Path,
    top_module: str,
    target_modules: list[str] | str | None = None,
    module_filter: str = "all",
) -> list[str]:
    paths = manual_paths(project_root, top_module)
    manifest = load_manifest(project_root, top_module)
    requested = _parse_module_list(target_modules)
    if requested:
        return requested

    module_names = set((manifest.get("base", {}).get("modules") or {}).keys())
    if paths["base_modules_dir"].exists():
        module_names.update(path.stem for path in paths["base_modules_dir"].glob("*.md"))
    names = sorted(name for name in module_names if name)

    normalized_filter = (module_filter or "all").strip().lower().replace("_", "-")
    if normalized_filter in {"all", "*"}:
        return names
    if normalized_filter == "retryable":
        return [
            name for name in names
            if _module_enhancement_state(paths["project_root"], manifest, name) in {"pending", "missing", "stale", "failed", "invalid"}
        ]
    if normalized_filter == "not-success":
        return [
            name for name in names
            if _module_enhancement_state(paths["project_root"], manifest, name) != "success"
        ]
    if normalized_filter in {"pending", "missing", "stale", "failed", "invalid", "success"}:
        return [
            name for name in names
            if _module_enhancement_state(paths["project_root"], manifest, name) == normalized_filter
        ]
    raise ValueError(f"unknown module enhancement filter: {module_filter}")


def _module_enhancement_state(project_root: Path, manifest: dict[str, Any], module_name: str) -> str:
    entry = enhancement_entry(manifest, "module", module_name)
    base_entry = base_target_entry(manifest, "module", module_name)
    if not entry:
        return "missing"
    status = entry.get("status") or "missing"
    if status == "success" and entry.get("base_hash") != base_entry.get("hash"):
        return "stale"
    enhanced_path = entry.get("enhanced_path") or ""
    if status == "success" and (not enhanced_path or not resolve_manifest_path(project_root, enhanced_path).exists()):
        return "missing"
    return status


def _parse_module_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = value.replace(";", ",").split(",")
    else:
        raw_items = []
        for item in value:
            raw_items.extend(str(item).replace(";", ",").split(","))
    return [item.strip() for item in raw_items if item.strip()]


def _log(event_logger: Callable[..., None] | None, event_type: str, **payload: Any) -> None:
    if event_logger is None:
        return
    try:
        event_logger(event_type, **payload)
    except Exception:
        pass
