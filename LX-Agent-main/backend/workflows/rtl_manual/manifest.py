from __future__ import annotations

from pathlib import Path
from typing import Any

from ..types import WorkflowContext, WorkflowStatus
from .artifacts import load_manifest, manual_paths

'''
RTL 手册工作流的运行时状态加载器
负责从清单文件中读取当前工作流的状态，并组装成 WorkflowStatus 对象返回
'''

def load_runtime_status(
    *,
    project_root: str | Path,
    top_module: str,
    context: WorkflowContext,
) -> WorkflowStatus:
    paths = manual_paths(project_root, top_module)
    manifest_exists = paths["manifest"].exists()
    manifest = load_manifest(project_root, top_module)
    artifacts = _artifact_paths(paths)
    warnings = _artifact_warnings(paths, manifest) if manifest_exists else []

    if not manifest_exists:
        return WorkflowStatus(
            workflow_id="rtl_manual",
            ok=True,
            run_id=context.run_id,
            status={
                "status": "not_initialized",
                "top_module": top_module,
                "base": {"status": "missing", "module_count": 0},
                "enhancements": {"main": "pending", "modules": _module_status_counts({})},
                "compose": {"status": "not_run"},
            },
            artifacts=artifacts,
            warnings=warnings,
        )

    base = manifest.get("base") or {}
    enhancements = manifest.get("enhancements") or {}
    compose = manifest.get("compose") or {}
    main_entry = (enhancements.get("main") or {}).get("main") or {}
    module_entries = enhancements.get("modules") or {}
    status = {
        "status": base.get("status") or "unknown",
        "top_module": manifest.get("top_module") or top_module,
        "base": {
            "status": base.get("status") or "unknown",
            "main": (base.get("main") or {}).get("path", ""),
            "modules_dir": artifacts["base_modules_dir"],
            "module_count": len(base.get("modules") or {}),
        },
        "source_review": manifest.get("source_review") or {"status": "not_run"},
        "enhancements": {
            "main": main_entry.get("status", "pending"),
            "modules": _module_status_counts(module_entries),
        },
        "compose": {
            "status": compose.get("status", "not_run"),
            "enhanced_count": compose.get("enhanced_count", 0),
            "fallback_count": compose.get("fallback_count", 0),
            "stale_count": compose.get("stale_count", 0),
            "invalid_count": compose.get("invalid_count", 0),
            "final_main": compose.get("final_main", ""),
            "final_modules_dir": compose.get("final_modules_dir", ""),
        },
        "review": manifest.get("review") or {"status": "not_run"},
    }
    return WorkflowStatus(
        workflow_id="rtl_manual",
        ok=True,
        run_id=context.run_id,
        status=status,
        artifacts=artifacts,
        warnings=warnings,
    )


def _artifact_paths(paths: dict[str, Path]) -> dict[str, str]:
    keys = (
        "base_main",
        "base_modules_dir",
        "enhanced_main",
        "enhanced_modules_dir",
        "final_main",
        "final_modules_dir",
        "review",
        "manifest",
    )
    return {key: str(paths[key]) for key in keys}


def _artifact_warnings(paths: dict[str, Path], manifest: dict[str, Any]) -> list[str]:
    warnings = []
    base = manifest.get("base") or {}
    compose = manifest.get("compose") or {}
    if base.get("status") == "ready":
        if not paths["base_main"].exists():
            warnings.append(f"Missing base main artifact: {paths['base_main']}")
        if not paths["base_modules_dir"].exists():
            warnings.append(f"Missing base modules artifact directory: {paths['base_modules_dir']}")
    if compose.get("status") == "success":
        if not paths["final_main"].exists():
            warnings.append(f"Missing final main artifact: {paths['final_main']}")
        if not paths["final_modules_dir"].exists():
            warnings.append(f"Missing final modules artifact directory: {paths['final_modules_dir']}")
    return warnings


def _module_status_counts(module_entries: dict[str, Any]) -> dict[str, int]:
    counts = {"pending": 0, "success": 0, "failed": 0, "stale": 0, "invalid": 0}
    for entry in module_entries.values():
        if not isinstance(entry, dict):
            continue
        status = entry.get("status", "pending")
        if status not in counts:
            continue
        counts[status] += 1
    return counts
