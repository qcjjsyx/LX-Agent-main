"""Build section-scoped context packs from split Manual IR exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .split_store import ManualIRSplitError, load_manifest, resolve_manual_ir_object, select_reading_path


def build_context_pack(
    manual_ir_dir: str | Path,
    *,
    reading_path_id: str | None = None,
    audience: str | None = None,
    section_id: str | None = None,
) -> Dict[str, Any]:
    """Build a deterministic evidence pack for one ReadingPath or section."""

    root = Path(manual_ir_dir)
    manifest = load_manifest(root)
    reading_path = select_reading_path(root, reading_path_id=reading_path_id, audience=audience)
    sections = list(reading_path.get("ordered_sections", []))
    if section_id:
        sections = [section for section in sections if section.get("section_id") == section_id]
        if not sections:
            raise ManualIRSplitError(f"ReadingSection not found: {section_id}")

    packed_sections = [
        _pack_section(root, section)
        for section in sections
    ]

    return {
        "schema": "manual_ir_context_pack",
        "schema_version": "0.1",
        "top_module": manifest.get("top_module", reading_path.get("top_module", "")),
        "manual_ir_dir": str(root),
        "generated_from": {
            "manual_ir_manifest": "manifest.json",
            "reading_path_id": reading_path.get("id", ""),
        },
        "reading_path": {
            "id": reading_path.get("id", ""),
            "audience": reading_path.get("audience", ""),
            "title": reading_path.get("title", ""),
            "summary": reading_path.get("summary", ""),
            "goals": list(reading_path.get("goals", [])),
            "must_cover": list(reading_path.get("must_cover", [])),
            "defer_sections": list(reading_path.get("defer_sections", [])),
            "risk_reminders": list(reading_path.get("risk_reminders", [])),
        },
        "sections": packed_sections,
        "warnings": _dedupe_text(
            warning
            for section in packed_sections
            for warning in section.get("warnings", [])
        ),
        "evidence_boundary": [
            "Use only covered_objects, semantic_overlays, and section metadata in this ContextPack as manual-writing evidence.",
            "When present, semantic_overlays are LLM-enriched Manual IR evidence and must preserve their evidence/confidence fields.",
            "Do not infer RTL process, always, FSM, or register behavior unless it is present as Manual IR/parser fact.",
            "Preserve partial FlowPath and low-confidence warnings instead of completing paths by guesswork.",
        ],
    }


def write_context_pack(path: str | Path, context_pack: Dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(context_pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pack_section(root: Path, section: Dict[str, Any]) -> Dict[str, Any]:
    covered_objects: List[Dict[str, Any]] = []
    semantic_overlays: List[Dict[str, Any]] = []
    unresolved_covers: List[str] = []
    warnings: List[str] = []
    source_refs: List[Dict[str, Any]] = []
    semantic_by_module = _load_semantic_module_cards(root)
    covered_semantic_ids: set[str] = set()

    for object_id in section.get("covers", []):
        try:
            obj = resolve_manual_ir_object(root, object_id)
        except (FileNotFoundError, ManualIRSplitError, json.JSONDecodeError):
            unresolved_covers.append(object_id)
            continue
        covered_objects.append(obj)
        warnings.extend(_object_warnings(obj))
        source_refs.extend(ref for ref in obj.get("source_refs", []) if isinstance(ref, dict))
        for module_name in _semantic_module_names_for_object(obj):
            semantic = semantic_by_module.get(module_name)
            if not semantic:
                continue
            semantic_id = str(semantic.get("id", ""))
            if semantic_id in covered_semantic_ids:
                continue
            covered_semantic_ids.add(semantic_id)
            semantic_overlays.append(semantic)
            source_refs.extend(ref for ref in semantic.get("source_refs", []) if isinstance(ref, dict))

    if unresolved_covers:
        warnings.append(f"unresolved covers: {', '.join(unresolved_covers)}")

    return {
        "section": section,
        "covered_objects": covered_objects,
        "semantic_overlays": semantic_overlays,
        "unresolved_covers": unresolved_covers,
        "warnings": _dedupe_text(warnings),
        "source_refs": _dedupe_source_refs(source_refs),
    }


def _load_semantic_module_cards(root: Path) -> Dict[str, Dict[str, Any]]:
    try:
        manifest = load_manifest(root)
    except Exception:
        return {}
    files = manifest.get("files", {}).get("semantic_module_cards", {})
    if not isinstance(files, dict):
        return {}
    semantic_cards: Dict[str, Dict[str, Any]] = {}
    for module_name, rel_path in files.items():
        if not isinstance(module_name, str) or not isinstance(rel_path, str):
            continue
        path = root / rel_path
        if not path.is_file():
            continue
        semantic_cards[module_name] = json.loads(path.read_text(encoding="utf-8"))
    return semantic_cards


def _semantic_module_names_for_object(obj: Dict[str, Any]) -> List[str]:
    kind = obj.get("kind")
    if kind == "module_card" and obj.get("module_name"):
        return [str(obj["module_name"])]
    if kind in {"channel_card", "flow_path"} and obj.get("scope_module"):
        return [str(obj["scope_module"])]
    return []


def _object_warnings(obj: Dict[str, Any]) -> List[str]:
    warnings = [
        f"{obj.get('id', '<unknown>')}: {warning}"
        for warning in obj.get("warnings", [])
        if isinstance(warning, str) and warning
    ]
    if obj.get("kind") == "flow_path" and obj.get("confidence") == "low":
        warnings.append(f"{obj.get('id', '<unknown>')}: low confidence FlowPath")
    return warnings


def _dedupe_text(values) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        if not isinstance(value, str) or not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _dedupe_source_refs(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped
