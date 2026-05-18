"""LLM-backed module-level semantic enrichment for split Manual IR."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Protocol

from .llm_client import OpenAICompatibleLLMClient
from .prompts import build_module_enrichment_messages
from .split_store import load_manifest


DEFAULT_CORE_MODULES = ("decoder", "launch", "execute", "lsu", "wb", "fetch", "intAndExc", "grf", "prf")
CONFIDENCE_LEVELS = {"high", "medium", "low"}
CLAIM_LIST_FIELDS = (
    "key_behaviors",
    "important_signals",
    "payload_semantics",
    "payload_field_semantics",
    "interface_semantics",
    "handshake_notes",
    "control_flow_notes",
    "state_or_register_behavior",
    "process_semantics",
    "assign_semantics",
    "signal_semantics",
)


class EnrichmentError(RuntimeError):
    """Raised when semantic enrichment cannot produce valid JSON output."""


class TextLLMClient(Protocol):
    def complete_text(self, messages: List[Dict[str, str]]) -> str:
        ...


def enrich_manual_ir(
    manual_ir_dir: str | Path,
    parser_artifacts_root: str | Path,
    *,
    modules: Iterable[str] | None = None,
    llm_client: TextLLMClient | None = None,
    skip_missing: bool = False,
    skip_failed: bool = False,
) -> Dict[str, Any]:
    """Enrich split Manual IR with semantic module cards.

    The function parses tagged LLM text into Python objects and validates the
    resulting semantic card before writing output, so malformed responses never
    corrupt the Manual IR directory.
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
        try:
            raw_output = _complete_llm_text(client, messages)
            parsed = _parse_tagged_semantic_text(raw_output, module_name=module_name, context=context)
            card = _validate_and_normalize_semantic_card(
                parsed,
                module_name=module_name,
                top_module=str(manifest.get("top_module", "")),
                input_hash=input_hash,
                source_refs=_semantic_source_refs(context),
            )
        except Exception as exc:
            issue = {
                "level": "warning" if skip_failed else "error",
                "code": "semantic_enrichment_failed",
                "message": f"Semantic enrichment failed for module {module_name}: {exc}",
                "module_name": module_name,
            }
            issues.append(issue)
            if skip_failed:
                continue
            raise
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
        "status": "passed" if prepared_cards and not any(item.get("level") == "error" for item in issues) else "failed",
    }
    return report


def _complete_llm_text(client: Any, messages: List[Dict[str, str]]) -> str:
    complete_text = getattr(client, "complete_text", None)
    if callable(complete_text):
        return complete_text(messages)
    complete_json = getattr(client, "complete_json", None)
    if callable(complete_json):
        return complete_json(messages)
    raise EnrichmentError("LLM client must provide complete_text(messages).")


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
            "rtl_semantic_slice_reference_format": (
                "Use file plus line_start/line_end from rtl_semantic_slices for "
                "always, initial, assign, case, register, or control-flow claims."
            ),
        },
        "parser_module": _trim_parser_module(parser_module),
        "manual_module_card": module_card,
        "related_channel_cards": channels,
        "related_flow_paths": flow_paths,
        "direct_component_contracts": contracts,
        "rtl_source_excerpt": rtl_excerpt,
        "rtl_semantic_slices": rtl_excerpt.get("semantic_slices", {}),
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
    semantic_slices = _extract_rtl_semantic_slices(
        lines=lines,
        module_start=start,
        module_end=end,
        file=str(rtl_file),
    )
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
        "semantic_slices": semantic_slices,
    }


def _extract_rtl_semantic_slices(
    *,
    lines: List[str],
    module_start: int,
    module_end: int,
    file: str,
) -> Dict[str, Any]:
    """Return focused source slices for LLM semantic extraction.

    This is intentionally lightweight. It does not prove RTL semantics; it only
    gives the enrichment LLM precise line-bounded evidence for process,
    assignment, and control-flow claims.
    """

    module_lines = lines[module_start - 1 : module_end]
    return {
        "file": file,
        "process_blocks": _extract_process_blocks(module_lines, module_start),
        "continuous_assignments": _extract_assignments(module_lines, module_start),
        "case_blocks": _extract_case_blocks(module_lines, module_start),
        "state_like_signals": _extract_state_like_signals(module_lines, module_start),
    }


def _extract_process_blocks(module_lines: List[str], first_line_number: int) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    process_start = re.compile(r"^\s*(always|initial)\b")
    boundary = re.compile(r"^\s*(always|initial|assign)\b|\bendmodule\b")
    index = 0
    while index < len(module_lines):
        line = module_lines[index]
        match = process_start.search(line)
        if not match:
            index += 1
            continue

        start = index
        end = index
        for cursor in range(index + 1, min(len(module_lines), index + 90)):
            current = module_lines[cursor]
            if cursor > index + 1 and boundary.search(current):
                break
            end = cursor
            if re.search(r"\bend\b", current) and _looks_like_process_end(module_lines[start : cursor + 1]):
                break

        blocks.append(
            {
                "process_id": f"process:{first_line_number + start}",
                "kind": match.group(1),
                "line_start": first_line_number + start,
                "line_end": first_line_number + end,
                "text": "\n".join(_numbered_lines(module_lines[start : end + 1], first_line_number + start)),
            }
        )
        index = end + 1
    return blocks[:12]


def _looks_like_process_end(lines: List[str]) -> bool:
    begin_count = sum(len(re.findall(r"\bbegin\b", line)) for line in lines)
    end_count = sum(len(re.findall(r"\bend\b", line)) for line in lines)
    return end_count >= begin_count


def _extract_assignments(module_lines: List[str], first_line_number: int) -> List[Dict[str, Any]]:
    assignments: List[Dict[str, Any]] = []
    index = 0
    while index < len(module_lines):
        if not re.search(r"^\s*assign\b", module_lines[index]):
            index += 1
            continue
        start = index
        collected = [module_lines[index]]
        while ";" not in module_lines[index] and index + 1 < len(module_lines):
            index += 1
            collected.append(module_lines[index])
        text = "\n".join(collected)
        lhs = ""
        match = re.search(r"\bassign\s+([^=]+?)\s*=", text, flags=re.DOTALL)
        if match:
            lhs = " ".join(match.group(1).split())
        assignments.append(
            {
                "assign_id": f"assign:{first_line_number + start}",
                "lhs": lhs,
                "line_start": first_line_number + start,
                "line_end": first_line_number + index,
                "text": "\n".join(_numbered_lines(collected, first_line_number + start)),
            }
        )
        index += 1
    return assignments[:30]


def _extract_case_blocks(module_lines: List[str], first_line_number: int) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    index = 0
    while index < len(module_lines):
        if not re.search(r"\bcase[zx]?\s*\(", module_lines[index]):
            index += 1
            continue
        start = index
        end = index
        for cursor in range(index + 1, min(len(module_lines), index + 90)):
            end = cursor
            if re.search(r"\bendcase\b", module_lines[cursor]):
                break
        blocks.append(
            {
                "case_id": f"case:{first_line_number + start}",
                "line_start": first_line_number + start,
                "line_end": first_line_number + end,
                "text": "\n".join(_numbered_lines(module_lines[start : end + 1], first_line_number + start)),
            }
        )
        index = end + 1
    return blocks[:12]


def _extract_state_like_signals(module_lines: List[str], first_line_number: int) -> List[Dict[str, Any]]:
    signals: List[Dict[str, Any]] = []
    pattern = re.compile(r"^\s*(?:reg|logic)\b(?P<body>.*?)(?:;|$)")
    state_words = re.compile(r"(state|fsm|cnt|count|flag|valid|ready|drive|free)", re.IGNORECASE)
    for offset, line in enumerate(module_lines):
        match = pattern.search(line)
        if not match:
            continue
        body = match.group("body")
        names = re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", body)
        names = [name for name in names if name not in {"signed", "wire", "reg", "logic"}]
        interesting = [name for name in names if state_words.search(name)]
        if not interesting:
            continue
        signals.append(
            {
                "line": first_line_number + offset,
                "signals": interesting,
                "declaration": line.strip(),
            }
        )
    return signals[:30]


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


SECTION_TO_FIELD = {
    "KEY_BEHAVIOR": "key_behaviors",
    "IMPORTANT_SIGNAL": "important_signals",
    "PAYLOAD_SEMANTIC": "payload_semantics",
    "PAYLOAD_FIELD_SEMANTIC": "payload_field_semantics",
    "INTERFACE_SEMANTIC": "interface_semantics",
    "HANDSHAKE_NOTE": "handshake_notes",
    "CONTROL_FLOW_NOTE": "control_flow_notes",
    "STATE_OR_REGISTER_BEHAVIOR": "state_or_register_behavior",
    "PROCESS_SEMANTIC": "process_semantics",
    "ASSIGN_SEMANTIC": "assign_semantics",
    "SIGNAL_SEMANTIC": "signal_semantics",
}
LIST_VALUE_FIELDS = {
    "signals",
    "instances",
    "fields",
    "related_payload",
    "reads",
    "writes",
    "consumers",
}
SECTION_FIELD_MAP = {
    "KEY_BEHAVIOR": ("name", "description", "signals", "instances"),
    "IMPORTANT_SIGNAL": ("signal", "role"),
    "PAYLOAD_SEMANTIC": ("payload", "description", "signals"),
    "PAYLOAD_FIELD_SEMANTIC": ("payload", "fields", "description"),
    "INTERFACE_SEMANTIC": ("name", "direction", "role", "related_payload"),
    "HANDSHAKE_NOTE": ("description", "signals"),
    "CONTROL_FLOW_NOTE": ("description", "signals"),
    "STATE_OR_REGISTER_BEHAVIOR": ("name", "description", "reads", "writes"),
    "PROCESS_SEMANTIC": ("process_id", "kind", "summary", "reads", "writes"),
    "ASSIGN_SEMANTIC": ("lhs", "rhs_summary", "role"),
    "SIGNAL_SEMANTIC": ("signal", "role", "producer", "consumers"),
}


def _parse_tagged_semantic_text(
    raw_output: str,
    *,
    module_name: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    sections = _collect_tagged_sections(raw_output)
    if not sections:
        raise EnrichmentError(f"LLM output for module {module_name} did not contain tagged semantic sections.")

    payload: Dict[str, Any] = {
        "purpose": None,
        "evidence_gaps": [],
    }
    for field in CLAIM_LIST_FIELDS:
        payload[field] = []

    for tag, data in sections:
        if tag == "PURPOSE":
            purpose = _build_claim_from_section(
                data,
                fields=("text",),
                module_name=module_name,
                context=context,
                allow_fallback_evidence=True,
            )
            if purpose is not None:
                payload["purpose"] = purpose
            continue

        if tag == "EVIDENCE_GAP":
            gap = _build_evidence_gap(data)
            if gap:
                payload["evidence_gaps"].append(gap)
            continue

        target_field = SECTION_TO_FIELD.get(tag)
        if not target_field:
            continue
        claim = _build_claim_from_section(
            data,
            fields=SECTION_FIELD_MAP[tag],
            module_name=module_name,
            context=context,
            allow_fallback_evidence=False,
        )
        if claim is not None:
            payload[target_field].append(claim)
        else:
            payload["evidence_gaps"].append(
                {
                    "field": target_field,
                    "reason": f"Skipped [{tag}] because it lacked supported content or evidence.",
                }
            )

    if not isinstance(payload.get("purpose"), dict):
        payload["purpose"] = _fallback_purpose_claim(context)
        payload["evidence_gaps"].append(
            {
                "field": "purpose",
                "reason": "LLM did not return a valid [PURPOSE] section; deterministic low-confidence fallback was used.",
            }
        )

    return payload


def _collect_tagged_sections(raw_output: str) -> List[tuple[str, Dict[str, str]]]:
    text = (raw_output or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:text|plaintext)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    sections: List[tuple[str, Dict[str, str]]] = []
    current_tag = ""
    current_data: Dict[str, str] = {}
    current_key = ""

    def commit() -> None:
        if current_tag and current_data:
            sections.append((current_tag, dict(current_data)))

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^\[([A-Za-z0-9_ -]+)\]$", stripped)
        if match:
            commit()
            current_tag = _normalize_tag(match.group(1))
            current_data = {}
            current_key = ""
            continue
        if not current_tag:
            continue
        if ":" in stripped:
            raw_key, value = stripped.split(":", 1)
            key = _normalize_key(raw_key)
            value = value.strip()
            if key in current_data and value:
                current_data[key] = f"{current_data[key]}; {value}"
            else:
                current_data[key] = value
            current_key = key
        elif current_key:
            current_data[current_key] = f"{current_data[current_key]} {stripped}".strip()

    commit()
    return sections


def _build_claim_from_section(
    data: Dict[str, str],
    *,
    fields: Iterable[str],
    module_name: str,
    context: Dict[str, Any],
    allow_fallback_evidence: bool,
) -> Dict[str, Any] | None:
    claim: Dict[str, Any] = {}
    for field in fields:
        value = data.get(field, "")
        if not value:
            continue
        if field in LIST_VALUE_FIELDS:
            claim[field] = _split_list_value(value)
        else:
            claim[field] = value

    if not claim:
        return None

    evidence = _parse_evidence_entries(data.get("evidence", ""))
    if not evidence and allow_fallback_evidence:
        evidence = _default_evidence(context, module_name)
    if not evidence:
        return None

    claim["confidence"] = _normalize_confidence(data.get("confidence", "low"))
    claim["evidence"] = evidence
    return claim


def _build_evidence_gap(data: Dict[str, str]) -> Dict[str, Any]:
    field = data.get("field", "").strip()
    reason = data.get("reason", "").strip()
    if not field and not reason:
        return {}
    gap: Dict[str, Any] = {}
    if field:
        gap["field"] = field
    if reason:
        gap["reason"] = reason
    evidence = _parse_evidence_entries(data.get("evidence", ""))
    if evidence:
        gap["evidence"] = evidence
    return gap


def _fallback_purpose_claim(context: Dict[str, Any]) -> Dict[str, Any]:
    module_name = str(context.get("module_name", ""))
    module_card = context.get("manual_module_card", {})
    summary = ""
    if isinstance(module_card, dict):
        summary = str(module_card.get("summary", "")).strip()
    text = summary or f"Module {module_name} has parser and RTL evidence, but its semantic purpose needs manual review."
    return {
        "text": text,
        "confidence": "low",
        "evidence": _default_evidence(context, module_name),
    }


def _default_evidence(context: Dict[str, Any], module_name: str) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = [
        {
            "source": f"modules/{module_name}.json",
            "path": "interface_summary",
        }
    ]
    module_card = context.get("manual_module_card", {})
    if isinstance(module_card, dict) and module_card.get("id"):
        evidence.append({"manual_ir_id": module_card.get("id")})
    rtl_excerpt = context.get("rtl_source_excerpt", {})
    if isinstance(rtl_excerpt, dict) and rtl_excerpt.get("available"):
        evidence.append(
            {
                "source": rtl_excerpt.get("file", ""),
                "line_start": rtl_excerpt.get("line_start", 0),
                "line_end": rtl_excerpt.get("line_end", 0),
            }
        )
    return evidence[:2]


def _parse_evidence_entries(value: str) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for item in _split_evidence_value(value):
        parsed = _parse_evidence_entry(item)
        if parsed:
            entries.append(parsed)
    return entries


def _split_evidence_value(value: str) -> List[str]:
    value = value.strip()
    if not value or value.lower() in {"none", "n/a", "unknown"}:
        return []
    separator = ";" if ";" in value else ","
    return [item.strip() for item in value.split(separator) if item.strip()]


def _parse_evidence_entry(item: str) -> Dict[str, Any]:
    item = item.strip()
    if not item:
        return {}
    manual_match = re.match(r"^(?:manual_ir_id|id)\s*:\s*(.+)$", item, flags=re.IGNORECASE)
    if manual_match:
        return {"manual_ir_id": manual_match.group(1).strip()}
    if "@" in item:
        source, path = item.split("@", 1)
        entry: Dict[str, Any] = {"source": source.strip()}
        if path.strip():
            entry["path"] = path.strip()
        return entry
    line_match = re.match(r"^(.+):(\d+)(?:-(\d+))?$", item)
    if line_match:
        line_start = int(line_match.group(2))
        line_end = int(line_match.group(3) or line_start)
        return {
            "source": line_match.group(1).strip(),
            "line_start": line_start,
            "line_end": line_end,
        }
    return {"source": item}


def _split_list_value(value: str) -> List[str]:
    return [
        item.strip()
        for item in re.split(r"[,;]", value)
        if item.strip() and item.strip().lower() not in {"none", "n/a", "unknown"}
    ]


def _normalize_confidence(value: str) -> str:
    confidence = value.strip().lower()
    return confidence if confidence in CONFIDENCE_LEVELS else "low"


def _normalize_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip().upper()).strip("_")


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


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
