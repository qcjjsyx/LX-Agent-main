"""Prompts for Manual IR semantic enrichment."""

from __future__ import annotations

import json
from typing import Any, Dict


SEMANTIC_MODULE_CARD_SCHEMA: Dict[str, Any] = {
    "id": "semantic_module:<module_name>",
    "kind": "semantic_module_card",
    "module_name": "<module_name>",
    "top_module": "<top_module>",
    "purpose": {
        "text": "",
        "confidence": "low|medium|high",
        "evidence": [],
    },
    "key_behaviors": [
        {
            "name": "",
            "description": "",
            "signals": [],
            "instances": [],
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "important_signals": [
        {
            "signal": "",
            "role": "",
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "payload_semantics": [],
    "payload_field_semantics": [
        {
            "payload": "",
            "fields": [],
            "description": "",
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "interface_semantics": [
        {
            "name": "",
            "direction": "",
            "role": "",
            "related_payload": [],
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "handshake_notes": [],
    "control_flow_notes": [],
    "state_or_register_behavior": [],
    "process_semantics": [
        {
            "process_id": "",
            "kind": "always|initial",
            "summary": "",
            "reads": [],
            "writes": [],
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "assign_semantics": [
        {
            "lhs": "",
            "rhs_summary": "",
            "role": "",
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "signal_semantics": [
        {
            "signal": "",
            "role": "",
            "producer": "",
            "consumers": [],
            "confidence": "low|medium|high",
            "evidence": [],
        }
    ],
    "evidence_gaps": [],
    "input_hash": "<filled_by_tool>",
}


def build_module_enrichment_messages(context: Dict[str, Any]) -> list[Dict[str, str]]:
    """Return chat messages for a tagged-text module semantic request."""

    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    module_name = context.get("module_name", "")

    system_prompt = (
        "You are an RTL/Verilog semantic enrichment engine for a Manual IR layer. "
        "You do not write user-facing manuals. You return tagged plain text fields, "
        "not JSON. The Python tool parses your tagged text and owns the final JSON "
        "Manual IR structure. "
        "Every semantic conclusion must be grounded in the supplied parser artifacts, "
        "Manual IR objects, or RTL source excerpt. Use confidence high, medium, or low. "
        "If evidence is missing or ambiguous, put that issue in evidence_gaps instead "
        "of guessing. Do not invent modules, signals, state machines, registers, "
        "pipeline stages, opcodes, exceptions, jumps, memory behavior, or writeback "
        "behavior unless the provided evidence supports it. Prefer RTL source excerpt "
        "and rtl_semantic_slices evidence for process, assign, register, and control-flow "
        "claims."
    )

    user_prompt = (
        f"Fill tagged semantic content for module {module_name}.\n\n"
        "Required output rules:\n"
        "- Do not output JSON, Markdown, tables, or code fences.\n"
        "- Output only the tagged sections described below.\n"
        "- Repeat a section when there are multiple claims of the same kind.\n"
        "- Use one `key: value` pair per line. Keep values on one line.\n"
        "- Use confidence: high, medium, or low.\n"
        "- Evidence is required for each claim. Separate multiple evidence entries with semicolons.\n"
        "- Evidence formats: `modules/<name>.json@interface_summary`, "
        "`manual_ir_id: module:<name>`, or `rtl/path/file.v:12-24`.\n"
        "- Keep output compact: at most 3 sections per repeated claim type and at most 2 evidence entries per section.\n"
        "- Use process_semantics for always/initial blocks, assign_semantics for "
        "continuous assignments, and payload_field_semantics only when bit ranges or "
        "signal grouping are visible in the supplied evidence.\n"
        "- Put unsupported but useful questions in [EVIDENCE_GAP].\n\n"
        "Tagged output protocol:\n"
        "[PURPOSE]\n"
        "text: <module purpose>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[KEY_BEHAVIOR]\n"
        "name: <short behavior name>\n"
        "description: <behavior description>\n"
        "signals: <signal>, <signal>\n"
        "instances: <instance>, <instance>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[IMPORTANT_SIGNAL]\n"
        "signal: <signal name>\n"
        "role: <signal role>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[PAYLOAD_SEMANTIC]\n"
        "payload: <payload name>\n"
        "description: <payload meaning>\n"
        "signals: <signal>, <signal>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[PAYLOAD_FIELD_SEMANTIC]\n"
        "payload: <payload name>\n"
        "fields: <field/range>, <field/range>\n"
        "description: <field meaning>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[INTERFACE_SEMANTIC]\n"
        "name: <interface or port name>\n"
        "direction: <input|output|inout|internal>\n"
        "role: <interface role>\n"
        "related_payload: <payload>, <payload>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[HANDSHAKE_NOTE]\n"
        "description: <handshake meaning>\n"
        "signals: <signal>, <signal>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[CONTROL_FLOW_NOTE]\n"
        "description: <control-flow meaning>\n"
        "signals: <signal>, <signal>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[STATE_OR_REGISTER_BEHAVIOR]\n"
        "name: <state/register/signal name>\n"
        "description: <state/register behavior>\n"
        "reads: <signal>, <signal>\n"
        "writes: <signal>, <signal>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[PROCESS_SEMANTIC]\n"
        "process_id: <process id from rtl_semantic_slices>\n"
        "kind: <always|initial>\n"
        "summary: <process behavior>\n"
        "reads: <signal>, <signal>\n"
        "writes: <signal>, <signal>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[ASSIGN_SEMANTIC]\n"
        "lhs: <left-hand side>\n"
        "rhs_summary: <right-hand side meaning>\n"
        "role: <assignment role>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[SIGNAL_SEMANTIC]\n"
        "signal: <signal name>\n"
        "role: <signal role>\n"
        "producer: <producer>\n"
        "consumers: <consumer>, <consumer>\n"
        "confidence: <high|medium|low>\n"
        "evidence: <evidence>; <evidence>\n\n"
        "[EVIDENCE_GAP]\n"
        "field: <field name>\n"
        "reason: <missing or ambiguous evidence>\n\n"
        "Input evidence context:\n"
        f"{context_text}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
