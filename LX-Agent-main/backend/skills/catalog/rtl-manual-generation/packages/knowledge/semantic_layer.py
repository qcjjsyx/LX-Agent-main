"""AI semantic enrichment for Knowledge IR.

The LLM returns tagged key-value text. This module parses and validates that
text, then writes stable JSON semantic cards. The model never writes JSON files
directly.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Protocol

try:
    from .llm_client import OpenAICompatibleLLMClient
except ImportError:  # pragma: no cover - supports direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from llm_client import OpenAICompatibleLLMClient


SCHEMA_VERSION = "0.2"
CONFIDENCE_LEVELS = {"high", "medium", "low"}
DOC_PRIORITIES = {"primary", "secondary", "reference"}
LIST_FIELDS = {
    "signals",
    "instances",
    "related_flows",
    "related_assignments",
    "related_payload",
    "consumers",
}
BOOLEAN_FIELDS = {"requires_rtl_source_review"}

MODULE_CLAIM_TAGS: Dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "MODULE_ROLE": (
        "module_role",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "related_flows", "doc_priority", "requires_rtl_source_review"),
    ),
    "STRUCTURAL_RESPONSIBILITY": (
        "structural_responsibility",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "related_flows", "doc_priority", "requires_rtl_source_review"),
    ),
    "COMPONENT_ROLE": (
        "component_role",
        ("subject", "summary"),
        ("explanation", "signals", "instances", "related_flows", "doc_priority", "requires_rtl_source_review"),
    ),
    "ASSIGNMENT_INTERPRETATION": (
        "assignment_interpretation",
        ("subject", "summary"),
        ("explanation", "signals", "related_assignments", "related_flows", "doc_priority", "requires_rtl_source_review"),
    ),
    "INTERFACE_INTENT": (
        "interface_intent",
        ("summary",),
        ("subject", "explanation", "signals", "related_payload", "doc_priority", "requires_rtl_source_review"),
    ),
    "DOCUMENTATION_FOCUS": (
        "documentation_focus",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "related_flows", "doc_priority", "requires_rtl_source_review"),
    ),
    "SOURCE_REVIEW_REQUEST": (
        "source_review_request",
        ("reason",),
        ("subject", "needed_source_slice", "signals", "instances", "related_flows", "doc_priority"),
    ),
}

FLOW_CLAIM_TAGS: Dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "FLOW_INTENT": (
        "flow_intent",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "related_assignments", "doc_priority", "requires_rtl_source_review"),
    ),
    "COMPONENT_ROLE": (
        "component_role",
        ("subject", "summary"),
        ("explanation", "signals", "instances", "related_assignments", "doc_priority", "requires_rtl_source_review"),
    ),
    "ASSIGNMENT_INTERPRETATION": (
        "assignment_interpretation",
        ("subject", "summary"),
        ("explanation", "signals", "related_assignments", "doc_priority", "requires_rtl_source_review"),
    ),
    "DATA_CONTROL_EFFECT": (
        "data_control_effect",
        ("summary",),
        ("subject", "explanation", "signals", "related_payload", "related_assignments", "doc_priority", "requires_rtl_source_review"),
    ),
    "COMPLETION_BACKPRESSURE": (
        "completion_backpressure",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "doc_priority", "requires_rtl_source_review"),
    ),
    "DOCUMENTATION_FOCUS": (
        "documentation_focus",
        ("summary",),
        ("subject", "explanation", "signals", "instances", "related_assignments", "doc_priority", "requires_rtl_source_review"),
    ),
    "SOURCE_REVIEW_REQUEST": (
        "source_review_request",
        ("reason",),
        ("subject", "needed_source_slice", "signals", "instances", "related_assignments", "doc_priority"),
    ),
}


class SemanticLayerError(RuntimeError):
    """Raised when Semantic Layer enrichment cannot proceed."""


class TextLLMClient(Protocol):
    def complete_text(self, messages: List[Dict[str, str]]) -> str:
        ...


def enrich_semantic_layer(
    knowledge_dir: str | Path,
    *,
    modules: Iterable[str] | None = None,
    include_flows: bool = True,
    max_flows_per_module: int | None = None,
    llm_client: TextLLMClient | None = None,
    skip_failed: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    knowledge_root = Path(knowledge_dir)
    manifest = read_json(knowledge_root / "manifest.json")
    ai_index = read_json(knowledge_root / "ai_context" / "index.json")
    top_module = str(manifest.get("top_module", ai_index.get("top_module", "")))
    selected_modules = select_modules(ai_index, modules)

    plan = build_enrichment_plan(
        knowledge_root,
        ai_index,
        selected_modules,
        include_flows=include_flows,
        max_flows_per_module=max_flows_per_module,
    )
    if dry_run:
        return {
            "schema": "knowledge_ir_semantic_report",
            "schema_version": SCHEMA_VERSION,
            "top_module": top_module,
            "status": "dry_run",
            "modules_requested": selected_modules,
            "planned_modules": len(plan["module_contexts"]),
            "planned_flows": len(plan["flow_contexts"]),
            "issues": [],
        }

    client = llm_client or OpenAICompatibleLLMClient()
    semantic_root = knowledge_root / "semantic"
    module_files: Dict[str, str] = {}
    flow_files: Dict[str, List[str]] = {}
    issues: List[Dict[str, Any]] = []
    module_cards: List[Dict[str, Any]] = []
    flow_cards: List[Dict[str, Any]] = []

    for module_name, context_path in plan["module_contexts"]:
        context = read_json(context_path)
        try:
            raw = client.complete_text(build_module_messages(context))
            card = parse_module_semantic_card(raw, context)
            rel_path = f"semantic/modules/{safe_filename(module_name)}.json"
            write_json(knowledge_root / rel_path, card)
            module_files[module_name] = rel_path
            module_cards.append(card)
        except Exception as exc:
            issue = {
                "level": "warning" if skip_failed else "error",
                "code": "module_semantic_failed",
                "module": module_name,
                "message": str(exc),
            }
            issues.append(issue)
            if not skip_failed:
                raise

    for module_name, flow_path in plan["flow_contexts"]:
        context = read_json(flow_path)
        flow_id = str(context.get("flow_id", flow_path.stem))
        try:
            raw = client.complete_text(build_flow_messages(context))
            card = parse_flow_semantic_card(raw, context)
            rel_path = (
                f"semantic/flows/{safe_filename(module_name)}/"
                f"{safe_filename(flow_id)}.json"
            )
            write_json(knowledge_root / rel_path, card)
            flow_files.setdefault(module_name, []).append(rel_path)
            flow_cards.append(card)
        except Exception as exc:
            issue = {
                "level": "warning" if skip_failed else "error",
                "code": "flow_semantic_failed",
                "module": module_name,
                "flow_id": flow_id,
                "message": str(exc),
            }
            issues.append(issue)
            if not skip_failed:
                raise

    status = semantic_status(issues)
    claim_counts = summarize_claims(module_cards + flow_cards)
    index = {
        "schema": "knowledge_ir_semantic_index",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "generated_from": {
            "knowledge_manifest": "manifest.json",
            "ai_context_index": "ai_context/index.json",
        },
        "counts": {
            "modules": len(module_files),
            "flows": sum(len(items) for items in flow_files.values()),
            "claims": sum(claim_counts.values()),
        },
        "claim_types": claim_counts,
        "files": {
            "modules": module_files,
            "flows": flow_files,
        },
        "issues": issues,
        "status": status,
    }
    write_json(semantic_root / "index.json", index)
    update_manifest_with_semantic(knowledge_root / "manifest.json", manifest, module_files, flow_files)

    report = {
        "schema": "knowledge_ir_semantic_report",
        "schema_version": SCHEMA_VERSION,
        "top_module": top_module,
        "status": status,
        "modules_requested": selected_modules,
        "semantic_module_cards": [card["id"] for card in module_cards],
        "semantic_flow_cards": [card["id"] for card in flow_cards],
        "count": {
            "modules": len(module_cards),
            "flows": len(flow_cards),
            "claims": sum(claim_counts.values()),
        },
        "claim_types": claim_counts,
        "issues": issues,
    }
    write_json(semantic_root / "semantic_report.json", report)
    return report


def build_enrichment_plan(
    knowledge_root: Path,
    ai_index: Dict[str, Any],
    selected_modules: List[str],
    *,
    include_flows: bool,
    max_flows_per_module: int | None,
) -> Dict[str, List[tuple[str, Path]]]:
    module_files = ai_index.get("files", {}).get("modules", {})
    flow_files = ai_index.get("files", {}).get("flows", {})
    module_contexts: List[tuple[str, Path]] = []
    flow_contexts: List[tuple[str, Path]] = []
    for module_name in selected_modules:
        rel_path = module_files.get(module_name) if isinstance(module_files, dict) else None
        if isinstance(rel_path, str):
            module_contexts.append((module_name, knowledge_root / rel_path))
        if not include_flows or not isinstance(flow_files, dict):
            continue
        rel_flows = flow_files.get(module_name, [])
        if not isinstance(rel_flows, list):
            continue
        if max_flows_per_module is not None and max_flows_per_module >= 0:
            rel_flows = rel_flows[:max_flows_per_module]
        for rel_flow in rel_flows:
            if isinstance(rel_flow, str):
                flow_contexts.append((module_name, knowledge_root / rel_flow))
    return {
        "module_contexts": module_contexts,
        "flow_contexts": flow_contexts,
    }


def select_modules(ai_index: Dict[str, Any], modules: Iterable[str] | None) -> List[str]:
    available = ai_index.get("files", {}).get("modules", {})
    available_names = sorted(available.keys()) if isinstance(available, dict) else []
    available_set = set(available_names)
    if modules is None:
        return available_names
    selected = [item.strip() for item in modules if item and item.strip()]
    if not selected:
        return available_names
    missing = [item for item in selected if item not in available_set]
    if missing:
        raise SemanticLayerError(f"Unknown module(s) in AI context index: {', '.join(missing)}")
    return selected


def build_module_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    module_name = context.get("module", "")
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    system_prompt = (
        "You are a Knowledge IR semantic claim engine for RTL manuals. "
        "Return tagged key-value text only. Do not return JSON, Markdown tables, or code fences. "
        "Do not restate deterministic facts such as port lists, widths, instance lists, or raw flow steps. "
        "Generate only reusable semantic claims that add interpretation for later manual generation. "
        "Every claim must be grounded in supplied AI context evidence. Use confidence high, medium, or low. "
        "If the compact context is insufficient for intent-level semantics, write SOURCE_REVIEW_REQUEST or "
        "EVIDENCE_GAP instead of guessing. "
        "All human-readable summary, explanation, and reason fields must be written in Simplified Chinese; "
        "keep module names, signal names, instance names, and field tags exactly as they appear in the RTL/context."
    )
    user_prompt = (
        f"Enrich module-level semantics for module {module_name}.\n\n"
        "The final RTL manual will be generated by another LLM from Knowledge IR plus these claims. "
        "Your job is not to write the manual and not to duplicate interface/flow facts. "
        "Return compact claims that explain role, intent, component meaning, assign impact, documentation focus, "
        "or evidence limitations.\n\n"
        "Output protocol. Repeat sections when useful, but keep compact.\n"
        "[MODULE_ROLE]\n"
        "subject: <module name or role candidate>\n"
        "summary: <one-sentence structural role or design-intent hypothesis>\n"
        "explanation: <why the supplied context supports this role>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[STRUCTURAL_RESPONSIBILITY]\n"
        "subject: <responsibility name>\n"
        "summary: <what this module structurally does>\n"
        "explanation: <how drive flow/interface/component evidence supports it>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[COMPONENT_ROLE]\n"
        "subject: <instance or component family>\n"
        "summary: <semantic role this component plays in the module>\n"
        "explanation: <how it shapes drive/data/control flow>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[ASSIGNMENT_INTERPRETATION]\n"
        "subject: <lhs signal or assign index>\n"
        "summary: <what this assign appears to contribute>\n"
        "explanation: <whether it affects data path, control path, drive gating, or intermediate signal shaping>\n"
        "signals: <signal>, <signal>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[INTERFACE_INTENT]\n"
        "subject: <interface group or boundary relation>\n"
        "summary: <semantic interpretation of a boundary group, not a port list>\n"
        "explanation: <how event/payload/free naming or contracts support the interpretation>\n"
        "signals: <signal>, <signal>\n"
        "related_payload: <payload signal>, <payload signal>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[DOCUMENTATION_FOCUS]\n"
        "subject: <manual focus area>\n"
        "summary: <what the final module manual should emphasize or de-emphasize>\n"
        "explanation: <why this focus follows from the context>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[SOURCE_REVIEW_REQUEST]\n"
        "subject: <claim or object that needs RTL source>\n"
        "reason: <why compact AI context is insufficient>\n"
        "needed_source_slice: <module declaration|assign block|instance connections|always block|comments>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_flows: <flow_id>, <flow_id>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[EVIDENCE_GAP]\n"
        "field: <field>\n"
        "reason: <missing or ambiguous evidence>\n\n"
        "Input AI context:\n"
        f"{context_text}"
    )
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def build_flow_messages(context: Dict[str, Any]) -> List[Dict[str, str]]:
    flow_id = context.get("flow_id", "")
    module_name = context.get("module", "")
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    system_prompt = (
        "You are a Knowledge IR flow semantic claim engine for RTL manuals. "
        "Return tagged key-value text only. Do not return JSON, Markdown tables, or code fences. "
        "Explain only the supplied single drive-based flow. Do not restate the raw step list or complete "
        "missing endpoints by guesswork. Generate compact interpretive claims for later manual generation. "
        "All human-readable summary, explanation, and reason fields must be written in Simplified Chinese; "
        "keep module names, signal names, instance names, flow ids, and field tags exactly as they appear in the RTL/context."
    )
    user_prompt = (
        f"Enrich flow semantics for module {module_name}, flow {flow_id}.\n\n"
        "The final RTL manual will be generated by another LLM from Knowledge IR plus these claims. "
        "Your job is to name and interpret the flow, component roles, assign effects, data/control coupling, "
        "and evidence limitations without duplicating deterministic flow facts.\n\n"
        "Output protocol. Repeat sections when useful, but keep compact.\n"
        "[FLOW_INTENT]\n"
        "subject: <flow id or event relation>\n"
        "summary: <one-sentence intent or structural meaning of this drive flow>\n"
        "explanation: <why the supplied flow/context supports this interpretation>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[COMPONENT_ROLE]\n"
        "subject: <instance or component family>\n"
        "summary: <semantic role inside this flow>\n"
        "explanation: <how this component buffers, selects, splits, merges, waits, or executes>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[ASSIGNMENT_INTERPRETATION]\n"
        "subject: <lhs signal or assign index>\n"
        "summary: <what the assign contributes to this flow>\n"
        "explanation: <whether it shapes payload, selector condition, drive gating, or intermediate control>\n"
        "signals: <signal>, <signal>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[DATA_CONTROL_EFFECT]\n"
        "subject: <payload/control relation>\n"
        "summary: <how data/control signals relate to the drive flow>\n"
        "explanation: <how payload contracts or assign dependencies support it>\n"
        "signals: <signal>, <signal>\n"
        "related_payload: <payload signal>, <payload signal>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[COMPLETION_BACKPRESSURE]\n"
        "subject: <free/backpressure/completion relation>\n"
        "summary: <what can be said about free/backpressure without overclaiming>\n"
        "explanation: <why this relation is or is not central for the final manual>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[DOCUMENTATION_FOCUS]\n"
        "subject: <manual focus area>\n"
        "summary: <what the final flow manual should emphasize or de-emphasize>\n"
        "explanation: <why this focus follows from the context>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "requires_rtl_source_review: <yes|no>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[SOURCE_REVIEW_REQUEST]\n"
        "subject: <claim or object that needs RTL source>\n"
        "reason: <why compact AI context is insufficient>\n"
        "needed_source_slice: <assign block|instance connections|always block|comments>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "related_assignments: <assign index>, <assign index>\n"
        "doc_priority: <primary|secondary|reference>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <source@path>; <source@path>\n\n"
        "[EVIDENCE_GAP]\n"
        "field: <field>\n"
        "reason: <missing or ambiguous evidence>\n\n"
        "Input flow AI context:\n"
        f"{context_text}"
    )
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def parse_module_semantic_card(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
    module_name = str(context.get("module", ""))
    payload: Dict[str, Any] = {
        "claims": [],
        "evidence_gaps": [],
    }

    for tag, data in collect_tagged_sections(raw_output):
        if tag == "EVIDENCE_GAP":
            gap = build_gap(data)
            if gap:
                payload["evidence_gaps"].append(gap)
            continue
        tag_spec = MODULE_CLAIM_TAGS.get(tag)
        if not tag_spec:
            continue
        claim_type, required_fields, optional_fields = tag_spec
        claim = build_semantic_claim(
            data,
            claim_type=claim_type,
            required_fields=required_fields,
            optional_fields=optional_fields,
            scope={"type": "module", "module": module_name},
        )
        if claim:
            payload["claims"].append(claim)
        else:
            payload["evidence_gaps"].append(
                {
                    "field": f"claims.{tag.lower()}",
                    "reason": f"Skipped invalid [{tag}] section because required text or evidence was missing.",
                }
            )

    if not payload["claims"]:
        payload["claims"].append(
            {
                "claim_type": "source_review_request",
                "scope": {"type": "module", "module": module_name},
                "subject": module_name,
                "reason": "The LLM output did not contain valid grounded semantic claims.",
                "needed_source_slice": "module declaration, instance connections, assign block, and comments",
                "doc_priority": "primary",
                "requires_rtl_source_review": True,
                "confidence": "low",
                "evidence": [{"source": f"ai_context/modules/{safe_filename(module_name)}.json", "path": "compact_context"}],
            }
        )
        payload["evidence_gaps"].append(
            {
                "field": "claims",
                "reason": "Missing valid semantic claim sections.",
            }
        )

    attach_claim_ids(payload["claims"], prefix=f"semantic:module:{module_name}")
    claim_summary = summarize_claims([payload])

    return {
        "schema": "knowledge_ir_module_semantic_claims",
        "schema_version": SCHEMA_VERSION,
        "id": f"semantic:module:{module_name}",
        "kind": "module_semantic_claims",
        "top_module": context.get("top_module", ""),
        "module": module_name,
        "input_hash": hash_json(context),
        "source_context": f"ai_context/modules/{safe_filename(module_name)}.json",
        "source_refs": semantic_source_refs(context),
        "claim_summary": {
            "count": sum(claim_summary.values()),
            "by_type": claim_summary,
        },
        **payload,
    }


def parse_flow_semantic_card(raw_output: str, context: Dict[str, Any]) -> Dict[str, Any]:
    module_name = str(context.get("module", ""))
    flow_id = str(context.get("flow_id", ""))
    payload: Dict[str, Any] = {
        "claims": [],
        "evidence_gaps": [],
    }

    for tag, data in collect_tagged_sections(raw_output):
        if tag == "EVIDENCE_GAP":
            gap = build_gap(data)
            if gap:
                payload["evidence_gaps"].append(gap)
            continue
        tag_spec = FLOW_CLAIM_TAGS.get(tag)
        if not tag_spec:
            continue
        claim_type, required_fields, optional_fields = tag_spec
        claim = build_semantic_claim(
            data,
            claim_type=claim_type,
            required_fields=required_fields,
            optional_fields=optional_fields,
            scope={"type": "flow", "module": module_name, "flow_id": flow_id},
        )
        if claim:
            payload["claims"].append(claim)
        else:
            payload["evidence_gaps"].append(
                {
                    "field": f"claims.{tag.lower()}",
                    "reason": f"Skipped invalid [{tag}] section because required text or evidence was missing.",
                }
            )

    if not payload["claims"]:
        payload["claims"].append(
            {
                "claim_type": "source_review_request",
                "scope": {"type": "flow", "module": module_name, "flow_id": flow_id},
                "subject": flow_id,
                "reason": "The LLM output did not contain valid grounded semantic claims for this flow.",
                "needed_source_slice": "related instance connections, assign block, and comments",
                "doc_priority": "primary",
                "requires_rtl_source_review": True,
                "confidence": "low",
                "evidence": [{"source": context_source_for_flow(module_name, flow_id), "path": "compact_context.flow"}],
            }
        )
        payload["evidence_gaps"].append(
            {
                "field": "claims",
                "reason": "Missing valid semantic claim sections.",
            }
        )

    attach_claim_ids(payload["claims"], prefix=f"semantic:flow:{module_name}:{flow_id}")
    claim_summary = summarize_claims([payload])

    return {
        "schema": "knowledge_ir_flow_semantic_claims",
        "schema_version": SCHEMA_VERSION,
        "id": f"semantic:flow:{module_name}:{flow_id}",
        "kind": "flow_semantic_claims",
        "top_module": context.get("top_module", ""),
        "module": module_name,
        "flow_id": flow_id,
        "input_hash": hash_json(context),
        "source_context": context_source_for_flow(module_name, flow_id),
        "source_refs": semantic_source_refs(context),
        "claim_summary": {
            "count": sum(claim_summary.values()),
            "by_type": claim_summary,
        },
        **payload,
    }


def build_semantic_claim(
    data: Dict[str, str],
    *,
    claim_type: str,
    required_fields: Iterable[str],
    optional_fields: Iterable[str],
    scope: Dict[str, str],
) -> Dict[str, Any] | None:
    claim: Dict[str, Any] = {
        "claim_type": claim_type,
        "scope": dict(scope),
    }
    for field in tuple(required_fields) + tuple(optional_fields):
        value = data.get(field, "").strip()
        if not value:
            continue
        if field in LIST_FIELDS:
            parsed_value: Any = split_list_value(value)
        elif field in BOOLEAN_FIELDS:
            parsed_value = parse_bool_value(value)
        elif field == "doc_priority":
            parsed_value = normalize_doc_priority(value)
        else:
            parsed_value = value
        if parsed_value not in ("", [], None):
            claim[field] = parsed_value

    missing_required = [field for field in required_fields if field not in claim]
    evidence = parse_evidence_entries(data.get("evidence", ""))
    if missing_required or not evidence:
        return None
    claim.setdefault("doc_priority", "reference")
    claim.setdefault("requires_rtl_source_review", claim_type == "source_review_request")
    claim["confidence"] = normalize_confidence(data.get("confidence", "low"))
    claim["evidence"] = evidence
    return claim


def attach_claim_ids(claims: List[Dict[str, Any]], *, prefix: str) -> None:
    type_counts: Dict[str, int] = {}
    for claim in claims:
        claim_type = str(claim.get("claim_type", "claim"))
        type_counts[claim_type] = type_counts.get(claim_type, 0) + 1
        claim["id"] = f"{prefix}:{safe_filename(claim_type)}:{type_counts[claim_type]:03d}"


def summarize_claims(cards: List[Dict[str, Any]]) -> Dict[str, int]:
    counter: Counter[str] = Counter()
    for card in cards:
        claims = card.get("claims", [])
        if not isinstance(claims, list):
            continue
        for claim in claims:
            if isinstance(claim, dict):
                counter[str(claim.get("claim_type", "unknown"))] += 1
    return dict(sorted(counter.items()))


def parse_bool_value(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "y", "required", "needs_review"}


def normalize_doc_priority(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in DOC_PRIORITIES else "reference"


def build_claim(
    data: Dict[str, str],
    *,
    fields: Iterable[str],
    allow_missing: bool,
) -> Dict[str, Any] | None:
    """Build a legacy free-form claim.

    Kept for compatibility with tests or scripts that import this helper
    directly; semantic cards now use build_semantic_claim().
    """
    claim: Dict[str, Any] = {}
    for field in fields:
        value = data.get(field, "").strip()
        if not value:
            continue
        if field in LIST_FIELDS:
            claim[field] = split_list_value(value)
        else:
            claim[field] = value
    if not claim and not allow_missing:
        return None
    evidence = parse_evidence_entries(data.get("evidence", ""))
    if not evidence and not allow_missing:
        return None
    claim["confidence"] = normalize_confidence(data.get("confidence", "low"))
    claim["evidence"] = evidence
    return claim


def collect_tagged_sections(raw_output: str) -> List[tuple[str, Dict[str, str]]]:
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
        tag_match = re.match(r"^\[([A-Za-z0-9_ -]+)\]$", stripped)
        if tag_match:
            commit()
            current_tag = normalize_tag(tag_match.group(1))
            current_data = {}
            current_key = ""
            continue
        if not current_tag:
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current_key = normalize_key(key)
            value = value.strip()
            if current_key in current_data and value:
                current_data[current_key] = f"{current_data[current_key]}; {value}"
            else:
                current_data[current_key] = value
        elif current_key:
            current_data[current_key] = f"{current_data[current_key]} {stripped}".strip()
    commit()
    return sections


def build_gap(data: Dict[str, str]) -> Dict[str, Any]:
    gap = {}
    if data.get("field", "").strip():
        gap["field"] = data["field"].strip()
    if data.get("reason", "").strip():
        gap["reason"] = data["reason"].strip()
    evidence = parse_evidence_entries(data.get("evidence", ""))
    if evidence:
        gap["evidence"] = evidence
    return gap


def parse_evidence_entries(value: str) -> List[Dict[str, Any]]:
    entries = []
    for item in split_evidence_value(value):
        if "@" in item:
            source, path = item.split("@", 1)
            entries.append({"source": source.strip(), "path": path.strip()})
        elif item:
            entries.append({"source": item})
    return entries


def split_evidence_value(value: str) -> List[str]:
    value = value.strip()
    if not value or value.lower() in {"none", "n/a", "unknown"}:
        return []
    separator = ";" if ";" in value else ","
    return [item.strip() for item in value.split(separator) if item.strip()]


def split_list_value(value: str) -> List[str]:
    return [
        item.strip()
        for item in re.split(r"[,;]", value)
        if item.strip() and item.strip().lower() not in {"none", "n/a", "unknown"}
    ]


def normalize_confidence(value: str) -> str:
    confidence = value.strip().lower()
    return confidence if confidence in CONFIDENCE_LEVELS else "low"


def normalize_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value.strip().upper()).strip("_")


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def context_source_for_flow(module_name: str, flow_id: str) -> str:
    return f"ai_context/modules/{safe_filename(module_name)}/flows/{safe_filename(flow_id)}.json"


def semantic_source_refs(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence_index = context.get("evidence_index", [])
    refs: List[Dict[str, Any]] = []
    if isinstance(evidence_index, list):
        for item in evidence_index:
            if isinstance(item, dict):
                refs.append(dict(item))
    source = context.get("source", {})
    if isinstance(source, dict) and source:
        refs.append({"id": "ai_context_source", "source": source})
    return refs


def semantic_status(issues: List[Dict[str, Any]]) -> str:
    if any(item.get("level") == "error" for item in issues):
        return "failed"
    if issues:
        return "passed_with_warnings"
    return "passed"


def update_manifest_with_semantic(
    manifest_path: Path,
    manifest: Dict[str, Any],
    module_files: Dict[str, str],
    flow_files: Dict[str, List[str]],
) -> None:
    files = manifest.setdefault("files", {})
    files["semantic"] = {
        "index": "semantic/index.json",
        "report": "semantic/semantic_report.json",
        "modules": module_files,
        "flows": flow_files,
    }
    counts = manifest.setdefault("counts", {})
    counts["semantic_modules"] = len(module_files)
    counts["semantic_flows"] = sum(len(items) for items in flow_files.values())
    write_json(manifest_path, manifest)


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hash_json(payload: Dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_filename(name: str) -> str:
    safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in name)
    return safe.strip("._") or "semantic"


def parse_modules_arg(value: str) -> List[str] | None:
    if not value.strip():
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AI semantic enrichment for Knowledge IR.")
    parser.add_argument("--knowledge-dir", default="rtl/knowledge_ir/arm_soc_top")
    parser.add_argument("--modules", default="", help="Comma-separated module names. Defaults to all modules.")
    parser.add_argument("--no-flows", action="store_true", help="Only enrich module overview contexts.")
    parser.add_argument("--max-flows-per-module", type=int, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--skip-failed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    client = None
    if not args.dry_run:
        client = OpenAICompatibleLLMClient(
            model=args.model,
            api_key=args.api_key,
            base_url=args.base_url,
        )
    report = enrich_semantic_layer(
        args.knowledge_dir,
        modules=parse_modules_arg(args.modules),
        include_flows=not args.no_flows,
        max_flows_per_module=args.max_flows_per_module,
        llm_client=client,
        skip_failed=args.skip_failed,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") in {"passed", "passed_with_warnings", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
