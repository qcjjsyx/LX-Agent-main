"""LLM-backed module-level semantic enrichment for split Manual IR."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Protocol

from .llm_client import OpenAICompatibleLLMClient
from .prompts import build_module_enrichment_messages
from .split_store import ManualIRSplitError, load_manifest


DEFAULT_CORE_MODULES = ("decoder", "launch", "execute", "lsu", "wb")
CONFIDENCE_LEVELS = {"high", "medium", "low"}
CLAIM_LIST_FIELDS = (
    "key_behaviors",
    "important_signals",
    "payload_semantics",
    "handshake_notes",
    "control_flow_notes",
    "state_or_register_behavior",
)


class EnrichmentError(RuntimeError):
    """Raised when semantic enrichment cannot produce valid JSON output."""


class JsonLLMClient(Protocol):
    def complete_json(self, messages: List[Dict[str, str]]) -> str:
        ...


def enrich_manual_ir(
    manual_ir_dir: str | Path,
    parser_artifacts_root: str | Path,
    *,
    modules: Iterable[str] | None = None,
    llm_client: JsonLLMClient | None = None,
    skip_missing: bool = False,
) -> Dict[str, Any]:
    """Enrich split Manual IR with semantic module cards.

    The function validates all LLM JSON before writing any output, so malformed
    responses never corrupt the Manual IR directory.
    """

    manual_root = Path(manual_ir_dir)
    artifacts_root = Path(parser_artifacts_root)
    manifest = load_manifest(manual_root)
    project_index = _load_json(artifacts_root / "project_index.json")
    selected_modules = _select_modules(modules, artifacts_root)
    client = llm_client or OpenAICompatibleLLMClient()

    issues: List[Dict[str, str]] = []
    prepared_cards: List[Dict[str, Any]] = []

    for module_name in selected_modules:
        module_artifact_path = artifacts_root / "modules" / f"{module_name}.json"
        if not module_artifact_path.is_file():
            issue = {
                "level": "warning" if skip_missing else "error",
                "code": "missing_parser_module",
                "message": f"Parser module artifact not found: modules/{module_name}.json",
                "module_name": module_name,
            }
            issues.append(issue)
            if skip_missing:
                continue
            raise EnrichmentError(issue["message"])

        context = build_module_enrichment_context(
            manual_root,
            artifacts_root,
            manifest,
            project_index,
            module_name,
        )
        input_hash = _hash_json(context)
        messages = build_module_enrichment_messages(context)
        raw_output = client.complete_json(messages)
        parsed = _parse_llm_json(raw_output, module_name)
        card = _validate_and_normalize_semantic_card(
            parsed,
            module_name=module_name,
            top_module=str(manifest.get("top_module", "")),
            input_hash=input_hash,
            source_refs=_semantic_source_refs(context),
        )
        prepared_cards.append(card)

    if prepared_cards:
        _write_semantic_cards(manual_root, prepared_cards)

    report = {
        "schema": "manual_ir_enrichment_report",
        "schema_version": "0.1",
        "manual_ir_dir": str(manual_root),
        "parser_artifacts_root": str(artifacts_root),
        "top_module": manifest.get("top_module", ""),
        "modules_requested": selected_modules,
        "semantic_module_cards": [card["id"] for card in prepared_cards],
        "count": len(prepared_cards),
        "issues": issues,
        "status": "passed" if not any(item.get("level") == "error" for item in issues) else "failed",
    }
    return report


def build_module_enrichment_context(
    manual_ir_dir: str | Path,
    parser_artifacts_root: str | Path,
    manifest: Dict[str, Any],
    project_index: Dict[str, Any],
    module_name: str,
) -> Dict[str, Any]:
    manual_root = Path(manual_ir_dir)
    artifacts_root = Path(parser_artifacts_root)
    parser_module = _load_json(artifacts_root / "modules" / f"{module_name}.json")
    module_card = _load_module_card(manual_root, manifest, module_name)
    channels = [
        item
        for item in _load_split_group(manual_root, manifest, "channel_cards")
        if item.get("scope_module") == module_name
    ]
    flow_paths = [
        item
        for item in _load_split_group(manual_root, manifest, "flow_paths")
        if item.get("scope_module") == module_name
    ]
    contracts = _contracts_for_module(manual_root, manifest, module_card)
    rtl_excerpt = _load_rtl_excerpt(project_index, parser_module, module_name, artifacts_root)

    return {
        "top_module": manifest.get("top_module", ""),
        "module_name": module_name,
        "source_ref_guide": {
            "parser_module_json": f"modules/{module_name}.json",
            "manual_module_card_id": module_card.get("id", ""),
            "rtl_file": rtl_excerpt.get("file", ""),
            "rtl_line_reference_format": "Use file plus line_start/line_end from rtl_source_excerpt.",
        },
        "parser_module": _trim_parser_module(parser_module),
        "manual_module_card": module_card,
        "related_channel_cards": channels,
        "related_flow_paths": flow_paths,
        "direct_component_contracts": contracts,
        "rtl_source_excerpt": rtl_excerpt,
    }


def _select_modules(modules: Iterable[str] | None, artifacts_root: Path) -> List[str]:
    if modules is None:
        candidates = list(DEFAULT_CORE_MODULES)
    else:
        candidates = [item.strip() for item in modules if item and item.strip()]
    if not candidates:
        candidates = list(DEFAULT_CORE_MODULES)
    return _dedupe(candidates)


def _trim_parser_module(parser_module: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema": parser_module.get("schema", ""),
        "name": parser_module.get("name", ""),
        "artifact_kind": parser_module.get("artifact_kind", ""),
        "module_role": parser_module.get("module_role", ""),
        "file": parser_module.get("file", ""),
        "interface": parser_module.get("interface", {}),
        "local_signals": parser_module.get("local_signals", []),
        "instances": parser_module.get("instances", []),
        "transparent_flows": parser_module.get("transparent_flows", []),
        "interface_summary": parser_module.get("interface_summary", {}),
        "direct_children": parser_module.get("direct_children", {}),
        "flow_graph": parser_module.get("flow_graph", {}),
        "transitive_summary": parser_module.get("transitive_summary", {}),
        "warnings": parser_module.get("warnings", []),
    }


def _load_module_card(manual_root: Path, manifest: Dict[str, Any], module_name: str) -> Dict[str, Any]:
    files = manifest.get("files", {}).get("module_cards", {})
    if not isinstance(files, dict):
        raise EnrichmentError("manifest.files.module_cards must be an object.")
    rel_path = files.get(module_name)
    if not isinstance(rel_path, str):
        raise EnrichmentError(f"Manual IR module card not found in manifest: {module_name}")
    return _load_json(manual_root / rel_path)


def _load_split_group(manual_root: Path, manifest: Dict[str, Any], group: str) -> List[Dict[str, Any]]:
    files = manifest.get("files", {}).get(group, {})
    if not isinstance(files, dict):
        return []
    items = []
    for _, rel_path in sorted(files.items()):
        if isinstance(rel_path, str) and (manual_root / rel_path).is_file():
            items.append(_load_json(manual_root / rel_path))
    return items


def _contracts_for_module(manual_root: Path, manifest: Dict[str, Any], module_card: Dict[str, Any]) -> List[Dict[str, Any]]:
    child_components = set(module_card.get("child_components", []))
    if not child_components:
        return []
    return [
        contract
        for contract in _load_split_group(manual_root, manifest, "component_contracts")
        if contract.get("component_name") in child_components
    ]


def _load_rtl_excerpt(
    project_index: Dict[str, Any],
    parser_module: Dict[str, Any],
    module_name: str,
    artifacts_root: Path,
) -> Dict[str, Any]:
    rtl_file = str(parser_module.get("file", ""))
    repo_root = Path(str(project_index.get("repo_root", ""))) if project_index.get("repo_root") else None
    candidates: List[Path] = []
    if rtl_file:
        path = Path(rtl_file)
        if path.is_absolute():
            candidates.append(path)
        if repo_root is not None:
            candidates.append(repo_root / rtl_file)
        candidates.append(artifacts_root.parent / rtl_file)

    source_path = next((path for path in candidates if path.is_file()), None)
    if source_path is None:
        return {
            "file": rtl_file,
            "available": False,
            "line_start": 0,
            "line_end": 0,
            "truncated": False,
            "text": "",
            "warning": f"RTL source file was not found for module {module_name}.",
        }

    lines = source_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start, end = _find_module_line_span(lines, module_name)
    excerpt_lines = lines[start - 1 : end]
    max_lines = 240
    truncated = len(excerpt_lines) > max_lines
    if truncated:
        head_count = 150
        tail_count = 70
        head = excerpt_lines[:head_count]
        tail = excerpt_lines[-tail_count:]
        text_lines = _numbered_lines(head, start)
        omitted_start = start + head_count
        omitted_end = end - tail_count
        text_lines.append(f"... omitted RTL lines {omitted_start}-{omitted_end} ...")
        text_lines.extend(_numbered_lines(tail, end - tail_count + 1))
    else:
        text_lines = _numbered_lines(excerpt_lines, start)

    return {
        "file": rtl_file,
        "available": True,
        "line_start": start,
        "line_end": end,
        "truncated": truncated,
        "text": "\n".join(text_lines),
    }


def _find_module_line_span(lines: List[str], module_name: str) -> tuple[int, int]:
    start_index = 0
    pattern = re.compile(rf"^\s*module\s+{re.escape(module_name)}\b")
    for index, line in enumerate(lines):
        if pattern.search(line):
            start_index = index
            break
    end_index = len(lines) - 1
    for index in range(start_index, len(lines)):
        if re.search(r"\bendmodule\b", lines[index]):
            end_index = index
            break
    return start_index + 1, end_index + 1


def _numbered_lines(lines: List[str], first_line_number: int) -> List[str]:
    return [
        f"{first_line_number + offset}: {line}"
        for offset, line in enumerate(lines)
    ]


def _parse_llm_json(raw_output: str, module_name: str) -> Dict[str, Any]:
    text = (raw_output or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise EnrichmentError(f"LLM output for module {module_name} was not valid JSON: {exc}") from exc
        else:
            raise EnrichmentError(f"LLM output for module {module_name} did not contain a JSON object.")
    if not isinstance(payload, dict):
        raise EnrichmentError(f"LLM output for module {module_name} must be a JSON object.")
    return payload


def _validate_and_normalize_semantic_card(
    payload: Dict[str, Any],
    *,
    module_name: str,
    top_module: str,
    input_hash: str,
    source_refs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    payload = dict(payload)
    if payload.get("module_name") not in ("", module_name, None):
        raise EnrichmentError(
            f"LLM output module_name mismatch: expected {module_name}, got {payload.get('module_name')}"
        )
    payload["id"] = f"semantic_module:{module_name}"
    payload["kind"] = "semantic_module_card"
    payload["module_name"] = module_name
    payload["top_module"] = top_module
    payload["input_hash"] = input_hash
    payload["source_refs"] = source_refs

    purpose = payload.get("purpose")
    if not isinstance(purpose, dict):
        raise EnrichmentError(f"semantic_module:{module_name}.purpose must be an object.")
    _validate_claim_object(purpose, f"semantic_module:{module_name}.purpose")

    for field in CLAIM_LIST_FIELDS:
        value = payload.setdefault(field, [])
        if not isinstance(value, list):
            raise EnrichmentError(f"semantic_module:{module_name}.{field} must be a list.")
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise EnrichmentError(f"semantic_module:{module_name}.{field}[{index}] must be an object.")
            _validate_claim_object(item, f"semantic_module:{module_name}.{field}[{index}]")

    evidence_gaps = payload.setdefault("evidence_gaps", [])
    if not isinstance(evidence_gaps, list):
        raise EnrichmentError(f"semantic_module:{module_name}.evidence_gaps must be a list.")

    return payload


def _validate_claim_object(claim: Dict[str, Any], path: str) -> None:
    confidence = claim.get("confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise EnrichmentError(f"{path}.confidence must be one of: high, medium, low.")
    evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise EnrichmentError(f"{path}.evidence must be a non-empty list.")


def _semantic_source_refs(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    module_name = str(context.get("module_name", ""))
    source_refs: List[Dict[str, Any]] = [
        {
            "artifact_kind": "module",
            "artifact_name": module_name,
            "json_ref": f"modules/{module_name}.json",
            "evidence_paths": [
                "interface",
                "instances",
                "interface_summary",
                "flow_graph",
                "direct_children",
            ],
        }
    ]
    module_card = context.get("manual_module_card", {})
    if isinstance(module_card, dict):
        source_refs.extend(ref for ref in module_card.get("source_refs", []) if isinstance(ref, dict))
    rtl_excerpt = context.get("rtl_source_excerpt", {})
    if isinstance(rtl_excerpt, dict) and rtl_excerpt.get("available"):
        source_refs.append(
            {
                "artifact_kind": "rtl_source",
                "artifact_name": module_name,
                "file": rtl_excerpt.get("file", ""),
                "line_start": rtl_excerpt.get("line_start", 0),
                "line_end": rtl_excerpt.get("line_end", 0),
            }
        )
    return _dedupe_dicts(source_refs)


def _write_semantic_cards(manual_root: Path, cards: List[Dict[str, Any]]) -> None:
    manifest = load_manifest(manual_root)
    semantic_dir = manual_root / "semantic_module_cards"
    semantic_dir.mkdir(parents=True, exist_ok=True)

    files = manifest.setdefault("files", {})
    if not isinstance(files, dict):
        raise EnrichmentError("manifest.files must be an object.")
    semantic_files = files.setdefault("semantic_module_cards", {})
    if not isinstance(semantic_files, dict):
        raise EnrichmentError("manifest.files.semantic_module_cards must be an object.")

    for card in cards:
        module_name = str(card.get("module_name", ""))
        file_name = f"{_safe_json_filename(module_name)}.json"
        rel_path = f"semantic_module_cards/{file_name}"
        _write_json_atomic(semantic_dir / file_name, card)
        semantic_files[module_name] = rel_path

    manifest.setdefault("counts", {})["semantic_module_cards"] = len(semantic_files)
    _update_manifest_indexes(manifest, cards)
    _write_json_atomic(manual_root / "manifest.json", manifest)


def _update_manifest_indexes(manifest: Dict[str, Any], cards: List[Dict[str, Any]]) -> None:
    indexes = manifest.setdefault("indexes", {})
    by_id = indexes.setdefault("by_id", {})
    by_module = indexes.setdefault("by_module", {})
    by_tag = indexes.setdefault("by_tag", {})
    if not isinstance(by_id, dict) or not isinstance(by_module, dict) or not isinstance(by_tag, dict):
        raise EnrichmentError("manifest.indexes.by_id/by_module/by_tag must be objects.")

    for card in cards:
        card_id = str(card.get("id", ""))
        module_name = str(card.get("module_name", ""))
        if not card_id or not module_name:
            continue
        by_id[card_id] = f"semantic_module_cards.{module_name}"
        by_module[module_name] = _dedupe(list(by_module.get(module_name, [])) + [card_id])
        by_tag["semantic_module_card"] = _dedupe(list(by_tag.get("semantic_module_card", [])) + [card_id])


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_json(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_json_filename(name: str) -> str:
    safe_name = "".join(char if char.isalnum() or char in "._-" else "_" for char in name)
    return safe_name.strip("._") or "manual_ir_object"


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _dedupe_dicts(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for value in values:
        key = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped
