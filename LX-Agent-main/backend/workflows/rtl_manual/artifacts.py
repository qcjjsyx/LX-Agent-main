from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "rtl_manual_enhancement_manifest"
MANIFEST_VERSION = "0.1"
TARGET_STATUSES = {"pending", "success", "failed", "stale", "invalid"}



'''
actions.py (workflow执行)
    ↓ 读写
artifacts.py (清单管理)
    ↓
enhancer.py, composer.py, reviewer.py 等模块
    ↓ 产出制品
文件系统中的 .md 文件们
'''

## 手册制品的路径
def manual_paths(project_root: str | Path, top_module: str) -> dict[str, Path]:
    root = Path(project_root).expanduser().resolve()
    manuals_dir = root / "docs" / "manuals"
    return {
        "project_root": root,
        "manuals_dir": manuals_dir,
        "base_main": manuals_dir / f"{top_module}_base.md",
        "base_modules_dir": manuals_dir / f"{top_module}_base_modules",
        "enhanced_main": manuals_dir / f"{top_module}_enhanced" / "main.md",
        "enhanced_modules_dir": manuals_dir / f"{top_module}_enhanced" / "modules",
        "final_main": manuals_dir / f"{top_module}_generated.md",
        "final_modules_dir": manuals_dir / f"{top_module}_generated_modules",
        "review": manuals_dir / f"{top_module}_generated_review.md",
        "manifest": manuals_dir / f"{top_module}_enhancement_manifest.json",
    }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

## 加载手册增强清单
def load_manifest(project_root: str | Path, top_module: str) -> dict[str, Any]:
    paths = manual_paths(project_root, top_module)
    manifest_path = paths["manifest"]
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return _normalize_manifest(payload, paths["project_root"], top_module)
    return _new_manifest(paths["project_root"], top_module)



## 保存手册增强清单
def save_manifest(project_root: str | Path, top_module: str, manifest: dict[str, Any]) -> Path:
    paths = manual_paths(project_root, top_module)
    manifest = _normalize_manifest(manifest, paths["project_root"], top_module)
    manifest["updated_at"] = now_iso()
    paths["manifest"].parent.mkdir(parents=True, exist_ok=True)
    paths["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return paths["manifest"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def refresh_base_manifest(project_root: str | Path, top_module: str, manifest: dict[str, Any]) -> dict[str, Any]:
    paths = manual_paths(project_root, top_module)
    root = paths["project_root"]
    manifest = _normalize_manifest(manifest, root, top_module)
    base = manifest.setdefault("base", {})
    base["status"] = "ready"
    base["built_at"] = now_iso()
    base["main"] = _base_file_entry(paths["base_main"], root)
    base_modules: dict[str, dict[str, Any]] = {}
    if paths["base_modules_dir"].exists():
        for path in sorted(paths["base_modules_dir"].glob("*.md")):
            base_modules[path.stem] = _base_file_entry(path, root)
    base["modules"] = base_modules

    _refresh_target_staleness(manifest, base)
    return manifest


def record_enhancement(
    project_root: str | Path,
    top_module: str,
    manifest: dict[str, Any],
    *,
    target_type: str,
    target_name: str,
    status: str,
    base_hash: str = "",
    enhanced_path: str | Path | None = None,
    model: str | None = None,
    error: str = "",
) -> dict[str, Any]:
    if status not in TARGET_STATUSES:
        raise ValueError(f"invalid enhancement status: {status}")
    paths = manual_paths(project_root, top_module)
    root = paths["project_root"]
    manifest = _normalize_manifest(manifest, root, top_module)
    target = _target_container(manifest, target_type)
    entry = {
        "target_type": target_type,
        "target_name": target_name,
        "status": status,
        "base_hash": base_hash,
        "enhanced_path": _relpath(Path(enhanced_path), root) if enhanced_path else "",
        "model": model or "",
        "updated_at": now_iso(),
        "error": error,
    }
    target[target_name] = entry
    return manifest


def mark_source_review_invalidated(project_root: str | Path, top_module: str) -> dict[str, Any]:
    manifest = load_manifest(project_root, top_module)
    base = manifest.setdefault("base", {})
    base["manual_context_status"] = "updated_after_base_by_source_review"
    manifest["source_review"] = {
        "status": "updated_manual_context",
        "updated_at": now_iso(),
        "requires_build": False,
        "requires_enhance": True,
        "requires_compose": True,
    }
    for entry in _all_target_entries(manifest):
        if entry.get("status") == "success":
            entry["status"] = "stale"
            entry["error"] = "Manual Context changed after source-review; rerun enhance and compose."
            entry["updated_at"] = now_iso()
    save_manifest(project_root, top_module, manifest)
    return manifest


def resolve_manifest_path(project_root: str | Path, path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path(project_root).expanduser().resolve() / path


def base_target_entry(manifest: dict[str, Any], target_type: str, target_name: str) -> dict[str, Any]:
    base = manifest.get("base", {})
    if target_type == "main":
        return dict(base.get("main") or {})
    return dict((base.get("modules") or {}).get(target_name) or {})


def enhancement_entry(manifest: dict[str, Any], target_type: str, target_name: str) -> dict[str, Any]:
    return _target_container(manifest, target_type).get(target_name) or {}


def update_compose_status(
    project_root: str | Path,
    top_module: str,
    manifest: dict[str, Any],
    *,
    enhanced_count: int,
    fallback_count: int,
    stale_count: int,
    invalid_count: int,
) -> dict[str, Any]:
    paths = manual_paths(project_root, top_module)
    root = paths["project_root"]
    manifest = _normalize_manifest(manifest, root, top_module)
    manifest["compose"] = {
        "status": "success",
        "composed_at": now_iso(),
        "final_main": _relpath(paths["final_main"], root),
        "final_modules_dir": _relpath(paths["final_modules_dir"], root),
        "enhanced_count": enhanced_count,
        "fallback_count": fallback_count,
        "stale_count": stale_count,
        "invalid_count": invalid_count,
    }
    return manifest


def _new_manifest(project_root: Path, top_module: str) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "schema": MANIFEST_SCHEMA,
        "schema_version": MANIFEST_VERSION,
        "workflow_id": "rtl_manual",
        "run_id": "",
        "top_module": top_module,
        "project_root": str(project_root),
        "created_at": timestamp,
        "updated_at": timestamp,
        "inputs": {"rtl_inputs": "rtl", "top_module": top_module, "base_hash": "", "manual_context_hash": ""},
        "base": {"status": "missing", "main": {}, "modules": {}},
        "source_review": {"status": "not_run", "report_path": "", "updated_context_hash": ""},
        "enhancements": {
            "main": {},
            "modules": {},
        },
        "compose": {},
        "review": {"status": "not_run", "report_path": "", "error": ""},
        "artifacts": _manifest_artifacts(project_root, top_module),
    }


def _normalize_manifest(payload: dict[str, Any], project_root: Path, top_module: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("schema", MANIFEST_SCHEMA)
    payload.setdefault("schema_version", MANIFEST_VERSION)
    payload.setdefault("workflow_id", "rtl_manual")
    payload.setdefault("run_id", "")
    payload.setdefault("top_module", top_module)
    payload.setdefault("project_root", str(project_root))
    payload.setdefault("created_at", now_iso())
    payload.setdefault("updated_at", now_iso())
    payload.setdefault("inputs", {})
    payload["inputs"].setdefault("rtl_inputs", "rtl")
    payload["inputs"].setdefault("top_module", top_module)
    payload["inputs"].setdefault("base_hash", "")
    payload["inputs"].setdefault("manual_context_hash", "")
    payload.setdefault("base", {"status": "missing", "main": {}, "modules": {}})
    payload["base"].setdefault("status", "missing")
    payload["base"].setdefault("main", {})
    payload["base"].setdefault("modules", {})
    payload.setdefault("source_review", {"status": "not_run", "report_path": "", "updated_context_hash": ""})
    payload["source_review"].setdefault("status", "not_run")
    payload["source_review"].setdefault("report_path", "")
    payload["source_review"].setdefault("updated_context_hash", "")
    payload.setdefault("enhancements", {})
    payload["enhancements"].setdefault("main", {})
    payload["enhancements"].setdefault("modules", {})
    payload.setdefault("compose", {})
    payload["compose"].setdefault("status", "not_run")
    payload.setdefault("review", {"status": "not_run", "report_path": "", "error": ""})
    payload["review"].setdefault("status", "not_run")
    payload["review"].setdefault("report_path", "")
    payload["review"].setdefault("error", "")
    payload.setdefault("artifacts", _manifest_artifacts(project_root, top_module))
    for key, value in _manifest_artifacts(project_root, top_module).items():
        payload["artifacts"].setdefault(key, value)
    return payload


def _manifest_artifacts(project_root: Path, top_module: str) -> dict[str, str]:
    paths = manual_paths(project_root, top_module)
    return {
        "base_main": _relpath(paths["base_main"], project_root),
        "base_modules_dir": _relpath(paths["base_modules_dir"], project_root),
        "enhanced_main": _relpath(paths["enhanced_main"], project_root),
        "enhanced_modules_dir": _relpath(paths["enhanced_modules_dir"], project_root),
        "final_main": _relpath(paths["final_main"], project_root),
        "final_modules_dir": _relpath(paths["final_modules_dir"], project_root),
        "review": _relpath(paths["review"], project_root),
        "manifest": _relpath(paths["manifest"], project_root),
    }


def _base_file_entry(path: Path, project_root: Path) -> dict[str, Any]:
    return {
        "path": _relpath(path, project_root),
        "hash": sha256_file(path) if path.exists() else "",
        "size": path.stat().st_size if path.exists() else 0,
    }


def _refresh_target_staleness(manifest: dict[str, Any], base: dict[str, Any]) -> None:
    main_hash = (base.get("main") or {}).get("hash", "")
    for entry in (manifest.get("enhancements", {}).get("main") or {}).values():
        if entry.get("status") == "success" and entry.get("base_hash") != main_hash:
            entry["status"] = "stale"
            entry["error"] = "Base main manual changed."
            entry["updated_at"] = now_iso()

    module_hashes = {
        name: item.get("hash", "")
        for name, item in (base.get("modules") or {}).items()
        if isinstance(item, dict)
    }
    module_targets = manifest.get("enhancements", {}).get("modules") or {}
    for name, entry in module_targets.items():
        if name not in module_hashes:
            entry["status"] = "stale"
            entry["error"] = "Base module page no longer exists."
            entry["updated_at"] = now_iso()
        elif entry.get("status") == "success" and entry.get("base_hash") != module_hashes[name]:
            entry["status"] = "stale"
            entry["error"] = "Base module page changed."
            entry["updated_at"] = now_iso()

    manifest["enhancements"]["main"].setdefault("main", {
        "target_type": "main",
        "target_name": "main",
        "status": "pending",
        "base_hash": main_hash,
        "enhanced_path": "",
        "model": "",
        "updated_at": now_iso(),
        "error": "",
    })
    for name, item in module_hashes.items():
        module_targets.setdefault(name, {
            "target_type": "module",
            "target_name": name,
            "status": "pending",
            "base_hash": item,
            "enhanced_path": "",
            "model": "",
            "updated_at": now_iso(),
            "error": "",
        })


def _target_container(manifest: dict[str, Any], target_type: str) -> dict[str, Any]:
    enhancements = manifest.setdefault("enhancements", {})
    if target_type == "main":
        return enhancements.setdefault("main", {})
    if target_type == "module":
        return enhancements.setdefault("modules", {})
    raise ValueError(f"unknown enhancement target_type: {target_type}")


def _all_target_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    enhancements = manifest.get("enhancements", {})
    entries = []
    entries.extend(item for item in (enhancements.get("main") or {}).values() if isinstance(item, dict))
    entries.extend(item for item in (enhancements.get("modules") or {}).values() if isinstance(item, dict))
    return entries


def _relpath(path: Path, project_root: Path) -> str:
    path = path.expanduser().resolve()
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
